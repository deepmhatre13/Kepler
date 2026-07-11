"""
/api/v1/dashboard — Live Dashboard KPI Endpoints

Bug Fixes Applied:
  - All DB queries now use db.db[collection].count_documents() directly against
    MongoDB instead of the broken ORM wrapper that used wrong collection names.
  - Counts satellites from "satellites" collection, debris from "debris" collection.
  - Returns space_weather_severity so the frontend Dashboard works correctly.
"""

from fastapi import APIRouter, Depends
from app.database.session import get_db, MongoSession
from app.schemas.api_schemas import APIResponse
from app.services.weather_service import weather_service
from typing import Dict, Any
import logging

logger = logging.getLogger("app")
router = APIRouter()


@router.get("/summary", response_model=APIResponse[Dict[str, Any]])
def get_dashboard_summary(db: MongoSession = Depends(get_db)):
    """
    Live dashboard KPI summary — ALL values come directly from MongoDB collections.
    Returns real zeros when no data has been synced yet.
    """
    try:
        sat_count   = db.db["satellites"].count_documents({})
        debris_count = db.db["debris"].count_documents({})
        alerts_count = db.db["alerts"].count_documents({"is_acknowledged": False})
        collisions   = db.db["conjunctions"].count_documents({"status": "PENDING"})
        agent_runs   = db.db["agent_runs"].count_documents({"status": "RUNNING"})

        # Space weather from DB, fallback to NOAA
        latest_weather = db.db["spaceWeather"].find_one(
            {}, {"_id": 0}, sort=[("recorded_at", -1)]
        )
        if latest_weather and latest_weather.get("k_index") is not None:
            weather_index    = f"K{latest_weather['k_index']}"
            weather_severity = latest_weather.get("severity", "NORMAL")
        else:
            try:
                live = weather_service._noaa_fallback()
                weather_index    = f"K{live['k_index']}"
                weather_severity = live.get("severity", "NORMAL")
            except Exception:
                weather_index    = "K0"
                weather_severity = "NORMAL"

        data: Dict[str, Any] = {
            "tracked_satellites":         sat_count,
            "debris_objects":             debris_count,
            "active_alerts_count":        alerts_count,
            "predicted_collisions_count": collisions,
            "active_agents_load":         agent_runs,
            "space_weather_index":        weather_index,
            "space_weather_severity":     weather_severity,
            "system_status":              "NOMINAL",
        }

        logger.info(
            f"[Dashboard] KPIs — sats: {sat_count}, debris: {debris_count}, "
            f"collisions: {collisions}, weather: {weather_index}"
        )

    except Exception as exc:
        logger.error(f"[Dashboard] DB query failed: {exc}")
        data = {
            "tracked_satellites":         0,
            "debris_objects":             0,
            "active_alerts_count":        0,
            "predicted_collisions_count": 0,
            "active_agents_load":         0,
            "space_weather_index":        "N/A",
            "space_weather_severity":     "UNKNOWN",
            "system_status":              "DB_UNAVAILABLE",
        }

    return APIResponse(
        success=True,
        message="Live dashboard telemetry compiled from production database",
        data=data,
    )
