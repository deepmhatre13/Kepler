"""
Space-Track Live Data Service
==============================
Fetches real GP (General Perturbations) data from Space-Track.org.
Upserts into MongoDB using NORAD catalog number as the unique key.

Bug Fixes Applied:
  1. Field names now match the Satellite / SpaceObject MongoDB model
     (noradId, objectName, objectType, etc.) instead of SQLAlchemy names.
  2. Lookups now use raw Mongo filter dicts instead of @property fields
     so queries actually hit the database.
  3. Satellite documents are populated with all orbital fields on insert.
  4. Structured logging at every pipeline stage.
"""

import httpx
import math
import datetime
import logging
from typing import List, Dict, Any, Optional
from app.database.session import MongoSession
from app.core.config import settings

logger = logging.getLogger("app")


# ---------------------------------------------------------------------------
# Sync group definitions: (group_name, objectType value in Mongo, description)
# ---------------------------------------------------------------------------
SYNC_GROUPS = [
    ("active",   "PAYLOAD", "Tracked active satellites"),
    ("starlink", "PAYLOAD", "Starlink constellation"),
    ("analyst",  "DEBRIS",  "Analyst debris objects"),
]


_TYPE_MAP = {
    "PAYLOAD":      "PAYLOAD",
    "ROCKET BODY":  "ROCKET_BODY",
    "DEBRIS":       "DEBRIS",
    "UNKNOWN":      "UNKNOWN",
}


def _semimajor_axis_from_mean_motion(mean_motion_revday: float) -> float:
    """Convert mean motion (rev/day) to semi-major axis (km)."""
    if mean_motion_revday <= 0:
        return 6778.0
    n_rads = mean_motion_revday * 2 * math.pi / 86400.0
    return (398600.4418 / (n_rads ** 2)) ** (1.0 / 3.0)


def _parse_epoch(epoch_str: str) -> Optional[str]:
    """Return ISO string or None — store as string in Mongo."""
    try:
        dt = datetime.datetime.fromisoformat(epoch_str.replace("Z", ""))
        return dt.isoformat()
    except Exception:
        return None


class SpaceTrackService:
    """
    Production Space-Track GP data service.
    Writes directly into MongoDB collections via MongoSession.
    """

    def __init__(self):
        self.username = settings.SPACETRACK_USERNAME
        self.password = settings.SPACETRACK_PASSWORD
        self.base_url = "https://www.space-track.org"
        self.client   = httpx.Client(timeout=60.0, follow_redirects=True)
        self._authenticated = False

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> bool:
        """Authenticate with Space-Track. Returns True on success."""
        if self._authenticated:
            return True

        if not self.username or not self.password:
            logger.warning(
                "SPACETRACK_USERNAME / SPACETRACK_PASSWORD not set — "
                "Space-Track calls will be skipped."
            )
            return False

        try:
            logger.info(f"[SpaceTrack] Authenticating as '{self.username}' …")
            resp = self.client.post(
                f"{self.base_url}/ajaxauth/login",
                data={"identity": self.username, "password": self.password},
            )
            logger.info(
                f"[SpaceTrack] Login response: HTTP {resp.status_code}, "
                f"cookies={list(self.client.cookies.keys())}"
            )
            if resp.status_code == 200 and "spacetrack_session" in self.client.cookies:
                self._authenticated = True
                logger.info("[SpaceTrack] ✅ Authentication successful.")
                return True

            logger.error(
                f"[SpaceTrack] ❌ Login failed — HTTP {resp.status_code}. "
                f"Body preview: {resp.text[:300]}"
            )
            return False
        except Exception as exc:
            logger.error(f"[SpaceTrack] ❌ Authentication exception: {exc}")
            return False

    def _reset_auth(self):
        """Force re-authentication on next call."""
        self._authenticated = False

    # ------------------------------------------------------------------
    # Raw API fetch
    # ------------------------------------------------------------------

    def fetch_group_json(self, group: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Fetch a named group from Space-Track. Returns list of GP records."""
        if not self.authenticate():
            logger.error(f"[SpaceTrack] Cannot fetch group '{group}' — auth failed.")
            return []

        if group == "active":
            path = f"/basicspacedata/query/class/gp/OBJECT_TYPE/PAYLOAD/decay_date/null-val/orderby/NORAD_CAT_ID/limit/{limit}/format/json"
        elif group == "starlink":
            path = f"/basicspacedata/query/class/gp/OBJECT_NAME/~~STARLINK/decay_date/null-val/orderby/NORAD_CAT_ID/limit/{limit}/format/json"
        elif group in ("analyst", "debris"):
            path = f"/basicspacedata/query/class/gp/OBJECT_TYPE/DEBRIS/decay_date/null-val/orderby/NORAD_CAT_ID/limit/{limit}/format/json"
        else:
            logger.warning(f"[SpaceTrack] Unknown group '{group}'.")
            return []

        url = f"{self.base_url}{path}"
        logger.info(f"[SpaceTrack] → GET {url}")

        try:
            resp = self.client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                logger.error(
                    f"[SpaceTrack] Unexpected response type {type(data)} — "
                    f"preview: {str(data)[:300]}"
                )
                # Session may have expired — force re-login next call
                self._reset_auth()
                return []
            logger.info(
                f"[SpaceTrack] ✅ Group '{group}': {len(data)} records received. "
                f"First record keys: {list(data[0].keys()) if data else 'N/A'}"
            )
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(
                f"[SpaceTrack] HTTP {exc.response.status_code} for group '{group}': "
                f"{exc.response.text[:300]}"
            )
            self._reset_auth()
            return []
        except Exception as exc:
            logger.error(f"[SpaceTrack] Fetch failed for group '{group}': {exc}")
            return []

    def fetch_by_catalog_json(self, catalog_number: str) -> Optional[Dict[str, Any]]:
        """Fetch a single object by NORAD catalog number."""
        if not self.authenticate():
            return None
        url = f"{self.base_url}/basicspacedata/query/class/gp/NORAD_CAT_ID/{catalog_number}/format/json"
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data[0] if isinstance(data, list) and data else None
        except Exception as exc:
            logger.error(f"[SpaceTrack] fetch_by_catalog({catalog_number}) failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # FIX #1 — Transform GP record → MongoDB document using correct field names
    # ------------------------------------------------------------------

    def _gp_to_satellite_doc(
        self, rec: Dict[str, Any], object_type_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Map a Space-Track GP JSON record to a MongoDB satellite/debris document.

        CRITICAL: Field names MUST match the MongoDB model (Satellite / SpaceObject)
        which uses camelCase (noradId, objectName, objectType, meanMotion …).
        The old code wrote snake_case (name, catalog_number, classification …) which
        were silently ignored by the Mongo adapter, leaving all collections empty.
        """
        norad_id     = str(rec.get("NORAD_CAT_ID", "")).strip()
        object_name  = rec.get("OBJECT_NAME", f"OBJ-{norad_id}").strip()
        raw_type     = rec.get("OBJECT_TYPE", "UNKNOWN")
        object_type  = object_type_override or _TYPE_MAP.get(raw_type, "UNKNOWN")

        mean_motion  = float(rec.get("MEAN_MOTION", 0) or 0)
        inclination  = float(rec.get("INCLINATION", 0) or 0)
        eccentricity = float(rec.get("ECCENTRICITY", 0) or 0)
        raan         = float(rec.get("RA_OF_ASC_NODE", 0) or 0)
        arg_perigee  = float(rec.get("ARG_OF_PERICENTER", 0) or 0)
        mean_anomaly = float(rec.get("MEAN_ANOMALY", 0) or 0)
        semimajor    = _semimajor_axis_from_mean_motion(mean_motion)
        period       = (1440.0 / mean_motion) if mean_motion > 0 else None
        epoch        = _parse_epoch(rec.get("EPOCH", ""))

        tle1 = rec.get("TLE_LINE1") or rec.get("LINE1")
        tle2 = rec.get("TLE_LINE2") or rec.get("LINE2")

        now = datetime.datetime.utcnow().isoformat()

        return {
            # ── Primary fields that match the MongoDB Satellite collection schema ──
            "noradId":      norad_id,
            "objectName":   object_name,
            "objectType":   object_type,
            "countryCode":  rec.get("COUNTRY_CODE", ""),
            "launchDate":   rec.get("LAUNCH_DATE", ""),
            "epoch":        epoch,
            "inclination":  inclination,
            "eccentricity": eccentricity,
            "meanMotion":   mean_motion,
            "source":       "space-track",
            "createdAt":    now,
            "updatedAt":    now,
            # ── Extended orbital elements ──
            "semimajor_axis":  semimajor,
            "period":          period,
            "raan":            raan,
            "arg_of_perigee":  arg_perigee,
            "mean_anomaly":    mean_anomaly,
            "tle_line1":       tle1,
            "tle_line2":       tle2,
            # ── Operational fields (satellites only) ──
            "status":           "ACTIVE",
            "fuel_percentage":  100.0,
            "operational_mode": "NORMAL",
        }

    # ------------------------------------------------------------------
    # FIX #2 — Use raw dict filter (not @property field) for Mongo lookups
    # ------------------------------------------------------------------

    def _find_by_norad(self, db: MongoSession, collection: str, norad_id: str):
        """Find a document by noradId using a raw dict filter (bypasses @property bug)."""
        return db.db[collection].find_one({"noradId": norad_id})

    def _upsert_satellite_doc(
        self, db: MongoSession, rec: Dict[str, Any], object_type_override: Optional[str] = None
    ) -> Optional[str]:
        """
        Upsert a Space-Track GP record into the satellites collection.
        Returns the noradId on success, None on failure.
        """
        norad_id = str(rec.get("NORAD_CAT_ID", "")).strip()
        if not norad_id:
            return None

        doc = self._gp_to_satellite_doc(rec, object_type_override)

        try:
            db.db["satellites"].update_one(
                {"noradId": norad_id},
                {"$set": doc},
                upsert=True,
            )
            return norad_id
        except Exception as exc:
            logger.warning(f"[SpaceTrack] Upsert failed for NORAD {norad_id}: {exc}")
            return None

    def _upsert_debris_doc(
        self, db: MongoSession, rec: Dict[str, Any]
    ) -> Optional[str]:
        """Upsert a debris record into the debris collection."""
        norad_id = str(rec.get("NORAD_CAT_ID", "")).strip()
        if not norad_id:
            return None

        doc = self._gp_to_satellite_doc(rec, object_type_override="DEBRIS")

        try:
            db.db["debris"].update_one(
                {"noradId": norad_id},
                {"$set": doc},
                upsert=True,
            )
            return norad_id
        except Exception as exc:
            logger.warning(f"[SpaceTrack] Debris upsert failed for NORAD {norad_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Public sync API
    # ------------------------------------------------------------------

    def sync_group(
        self,
        db: MongoSession,
        group: str,
        object_type_override: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> int:
        """Fetch a group and upsert all records into MongoDB. Returns count inserted/updated."""
        records = self.fetch_group_json(group, limit=limit or 500)
        if not records:
            logger.warning(f"[SpaceTrack] sync_group('{group}'): 0 records — nothing to upsert.")
            return 0

        logger.info(f"[SpaceTrack] sync_group('{group}'): upserting {len(records)} records …")
        count = 0
        is_debris = (object_type_override == "DEBRIS" or group in ("analyst", "debris"))

        for i, rec in enumerate(records):
            try:
                if is_debris:
                    result = self._upsert_debris_doc(db, rec)
                else:
                    result = self._upsert_satellite_doc(db, rec, object_type_override)

                if result:
                    count += 1
                    if i < 3:  # Log first few for verification
                        logger.info(
                            f"[SpaceTrack]   ✓ Upserted NORAD {result} "
                            f"({rec.get('OBJECT_NAME', '?')})"
                        )
            except Exception as exc:
                logger.warning(
                    f"[SpaceTrack] Record {i} (NORAD {rec.get('NORAD_CAT_ID', '?')}) "
                    f"upsert error: {exc}"
                )

        logger.info(f"[SpaceTrack] ✅ sync_group('{group}') complete: {count}/{len(records)} upserted.")
        return count

    def sync_all_groups(self, db: MongoSession, limit_per_group: int = 500) -> Dict[str, int]:
        """Sync all configured groups. Returns {group: count}."""
        results = {}
        for group, type_override, desc in SYNC_GROUPS:
            logger.info(f"[SpaceTrack] ── Syncing: {group} ({desc})")
            results[group] = self.sync_group(db, group, type_override, limit=limit_per_group)
        total = sum(results.values())
        logger.info(f"[SpaceTrack] 🏁 All groups synced. Total upserted: {total}. Details: {results}")
        return results

    def sync_by_catalog(self, db: MongoSession, catalog_number: str) -> Optional[Dict]:
        """Fetch and upsert a single object by catalog number. Returns the doc."""
        rec = self.fetch_by_catalog_json(catalog_number)
        if not rec:
            return None
        obj_type = _TYPE_MAP.get(rec.get("OBJECT_TYPE", "UNKNOWN"), "UNKNOWN")
        if obj_type == "DEBRIS":
            self._upsert_debris_doc(db, rec)
        else:
            self._upsert_satellite_doc(db, rec, obj_type)
        return self._find_by_norad(db, "satellites", catalog_number) or \
               self._find_by_norad(db, "debris", catalog_number)

    def get_stats(self, db: MongoSession) -> Dict[str, Any]:
        """Return satellite/debris count statistics from MongoDB."""
        try:
            sat_total   = db.db["satellites"].count_documents({})
            payload_ct  = db.db["satellites"].count_documents({"objectType": "PAYLOAD"})
            debris_ct   = db.db["debris"].count_documents({})
            rocket_ct   = db.db["satellites"].count_documents({"objectType": "ROCKET_BODY"})
            unknown_ct  = db.db["satellites"].count_documents({"objectType": "UNKNOWN"})

            logger.info(
                f"[SpaceTrack] DB stats — satellites: {sat_total}, "
                f"payload: {payload_ct}, debris: {debris_ct}, "
                f"rocket_bodies: {rocket_ct}, unknown: {unknown_ct}"
            )
            return {
                "total":         sat_total + debris_ct,
                "payloads":      payload_ct,
                "debris":        debris_ct,
                "rocket_bodies": rocket_ct,
                "unknown":       unknown_ct,
                "last_sync":     datetime.datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error(f"[SpaceTrack] get_stats failed: {exc}")
            return {"total": 0, "payloads": 0, "debris": 0, "rocket_bodies": 0, "unknown": 0}


spacetrack_service = SpaceTrackService()
