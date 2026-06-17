"""
Space-Track Live Data Service
==============================
Fetches real GP (General Perturbations) data from Space-Track.org.
Supports active satellites, debris, and Starlink constellations.
Upserts into SQLite/PostgreSQL using NORAD catalog number as the unique key.
"""

import httpx
import math
import datetime
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.db_models import SpaceObject, Satellite, Debris
from app.core.config import settings

logger = logging.getLogger("app")


SYNC_GROUPS = [
    ("active",    "PAYLOAD",     "Tracked active satellites"),
    ("starlink",  "PAYLOAD",     "Starlink constellation"),
    ("analyst",   "DEBRIS",      "Analyst debris objects"),
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


def _parse_epoch(epoch_str: str) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.fromisoformat(epoch_str.replace("Z", ""))
    except Exception:
        return None


class SpaceTrackService:
    """
    Production Space-Track GP data service.
    Replaces CelesTrak service with direct authenticated calls.
    """

    def __init__(self):
        self.username = settings.SPACETRACK_USERNAME
        self.password = settings.SPACETRACK_PASSWORD
        self.base_url = "https://www.space-track.org"
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)
        self.session_cookie = None

    def authenticate(self) -> bool:
        """Authenticate with Space-Track and store session cookie."""
        if not self.username or not self.password:
            logger.warning("Space-Track credentials not set. API calls will fail.")
            return False

        if self.session_cookie:
            return True

        try:
            resp = self.client.post(
                f"{self.base_url}/ajaxauth/login",
                data={"identity": self.username, "password": self.password}
            )
            if resp.status_code == 200:
                
                self.session_cookie = resp.cookies.get("spacetrack_session") or self.client.cookies.get("spacetrack_session")
                if self.session_cookie:
                    logger.info("Successfully authenticated with Space-Track.")
                    return True
            logger.error(f"Space-Track login failed with status {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Space-Track authentication error: {e}")
            return False

    def fetch_group_json(self, group: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Fetch a named group from Space-Track using filters."""
        if not self.authenticate():
            logger.error(f"Cannot fetch group '{group}' because Space-Track authentication failed.")
            return []

        
        if group == "active":
            query_path = f"/basicspacedata/query/class/gp/OBJECT_TYPE/PAYLOAD/decay_date/null-val/orderby/NORAD_CAT_ID/limit/{limit}/format/json"
        elif group == "starlink":
            query_path = f"/basicspacedata/query/class/gp/OBJECT_NAME/~~STARLINK/decay_date/null-val/orderby/NORAD_CAT_ID/limit/{limit}/format/json"
        elif group == "analyst" or group == "debris":
            query_path = f"/basicspacedata/query/class/gp/OBJECT_TYPE/DEBRIS/decay_date/null-val/orderby/NORAD_CAT_ID/limit/{limit}/format/json"
        else:
            logger.warning(f"Unknown group '{group}' requested. Defaulting to empty query.")
            return []

        url = f"{self.base_url}{query_path}"
        logger.info(f"Space-Track → fetching group '{group}' from {url}")
        try:
            resp = self.client.get(url, cookies={"spacetrack_session": self.session_cookie})
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Space-Track → received {len(data)} records for group '{group}'")
            return data
        except Exception as e:
            logger.error(f"Space-Track fetch failed for group '{group}': {e}")
            return []

    def fetch_by_catalog_json(self, catalog_number: str) -> Optional[Dict[str, Any]]:
        """Fetch a single object by catalog number."""
        if not self.authenticate():
            return None

        url = f"{self.base_url}/basicspacedata/query/class/gp/NORAD_CAT_ID/{catalog_number}/format/json"
        try:
            resp = self.client.get(url, cookies={"spacetrack_session": self.session_cookie})
            resp.raise_for_status()
            data = resp.json()
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Space-Track fetch by CATNR={catalog_number} failed: {e}")
            return None

    def fetch_by_name_json(self, name: str) -> List[Dict[str, Any]]:
        """Fetch objects matching a name pattern."""
        if not self.authenticate():
            return []

        url = f"{self.base_url}/basicspacedata/query/class/gp/OBJECT_NAME/~~{name}/orderby/NORAD_CAT_ID/format/json"
        try:
            resp = self.client.get(url, cookies={"spacetrack_session": self.session_cookie})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Space-Track fetch by NAME={name} failed: {e}")
            return []

    def _gp_to_space_object_fields(
        self, rec: Dict[str, Any], classification_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Map a Space-Track GP JSON record to SpaceObject column values."""
        norad_id    = str(rec.get("NORAD_CAT_ID", ""))
        name        = rec.get("OBJECT_NAME", f"OBJ-{norad_id}").strip()
        obj_type    = rec.get("OBJECT_TYPE", "UNKNOWN")
        classification = classification_override or _TYPE_MAP.get(obj_type, "UNKNOWN")

        mean_motion = float(rec.get("MEAN_MOTION", 0) or 0)
        inclination = float(rec.get("INCLINATION", 0) or 0)
        eccentricity = float(rec.get("ECCENTRICITY", 0) or 0)
        raan         = float(rec.get("RA_OF_ASC_NODE", 0) or 0)
        arg_perigee  = float(rec.get("ARG_OF_PERICENTER", 0) or 0)
        mean_anomaly = float(rec.get("MEAN_ANOMALY", 0) or 0)
        semimajor    = _semimajor_axis_from_mean_motion(mean_motion)
        period       = (1440.0 / mean_motion) if mean_motion > 0 else None
        epoch        = _parse_epoch(rec.get("EPOCH", ""))

        tle1 = rec.get("TLE_LINE1") or rec.get("LINE1")
        tle2 = rec.get("TLE_LINE2") or rec.get("LINE2")

        return {
            "name":            name,
            "catalog_number":  norad_id,
            "cospar_id":       rec.get("OBJECT_ID", ""),
            "classification":  classification,
            "epoch":           epoch,
            "inclination":     inclination,
            "eccentricity":    eccentricity,
            "semimajor_axis":  semimajor,
            "raan":            raan,
            "arg_of_perigee":  arg_perigee,
            "mean_anomaly":    mean_anomaly,
            "mean_motion":     mean_motion,
            "period":          period,
            "tle_line1":       tle1,
            "tle_line2":       tle2,
            "updated_at":      datetime.datetime.utcnow(),
        }

    def upsert_space_object(
        self, db: Session, rec: Dict[str, Any], classification_override: Optional[str] = None
    ) -> SpaceObject:
        """Insert or update a SpaceObject from a GP record. Returns the DB object."""
        norad_id = str(rec.get("NORAD_CAT_ID", ""))
        if not norad_id:
            return None

        fields = self._gp_to_space_object_fields(rec, classification_override)
        obj = db.query(SpaceObject).filter(SpaceObject.catalog_number == norad_id).first()

        if obj:
            for k, v in fields.items():
                if v is not None:
                    setattr(obj, k, v)
        else:
            obj = SpaceObject(**fields)
            db.add(obj)
            db.flush()

        return obj

    def sync_group(
        self,
        db: Session,
        group: str,
        classification_override: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> int:
        """Fetch a group and upsert all records into the DB."""
        records = self.fetch_group_json(group, limit=limit or 500)

        count = 0
        for rec in records:
            try:
                obj = self.upsert_space_object(db, rec, classification_override)
                if obj:
                    
                    if obj.classification == "PAYLOAD" and not obj.satellite_details:
                        sat = Satellite(
                            space_object_id=obj.id,
                            status="ACTIVE",
                            fuel_percentage=100.0,
                            operational_mode="NORMAL",
                        )
                        db.add(sat)
                    
                    elif obj.classification in ("DEBRIS", "ROCKET_BODY") and not obj.debris_details:
                        debris = Debris(space_object_id=obj.id)
                        db.add(debris)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert NORAD {rec.get('NORAD_CAT_ID')}: {e}")
                db.rollback()
                continue

        try:
            db.commit()
            logger.info(f"✅ Space-Track sync '{group}': {count} objects upserted.")
        except Exception as e:
            db.rollback()
            logger.error(f"DB commit failed for group '{group}': {e}")

        return count

    def sync_all_groups(self, db: Session, limit_per_group: int = 500) -> Dict[str, int]:
        """Sync all configured groups. Returns dict of {group: count}."""
        results = {}
        for group, cls_override, desc in SYNC_GROUPS:
            logger.info(f"Syncing group: {group} ({desc})")
            count = self.sync_group(db, group, cls_override, limit=limit_per_group)
            results[group] = count
        return results

    def sync_by_catalog(self, db: Session, catalog_number: str) -> Optional[SpaceObject]:
        """Fetch and upsert a single object by catalog number."""
        rec = self.fetch_by_catalog_json(catalog_number)
        if not rec:
            return None
        obj = self.upsert_space_object(db, rec)
        db.commit()
        return obj

    def get_stats(self, db: Session) -> Dict[str, Any]:
        """Return quick statistics about what's in the DB."""
        total     = db.query(SpaceObject).count()
        payloads  = db.query(SpaceObject).filter(SpaceObject.classification == "PAYLOAD").count()
        debris    = db.query(SpaceObject).filter(SpaceObject.classification == "DEBRIS").count()
        rockets   = db.query(SpaceObject).filter(SpaceObject.classification == "ROCKET_BODY").count()
        unknown   = db.query(SpaceObject).filter(SpaceObject.classification == "UNKNOWN").count()
        return {
            "total": total,
            "payloads": payloads,
            "debris": debris,
            "rocket_bodies": rockets,
            "unknown": unknown,
            "last_sync": datetime.datetime.utcnow().isoformat(),
        }



spacetrack_service = SpaceTrackService()
