"""
/api/v1/catalog — Live Orbital Catalog Endpoints
Exposes Space-Track data: satellites, debris, rocket bodies, and manual sync triggers.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database.session import get_db
from app.models.db_models import SpaceObject, Satellite, Debris
from app.schemas.api_schemas import APIResponse, PaginationSchema
from app.services.spacetrack import spacetrack_service, SYNC_GROUPS

router = APIRouter()





@router.get("/objects", response_model=APIResponse[List[Dict[str, Any]]])
def list_space_objects(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    classification: Optional[str] = Query(None, description="PAYLOAD | DEBRIS | ROCKET_BODY | UNKNOWN"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List all tracked space objects with orbital elements."""
    query = db.query(SpaceObject)

    if classification:
        query = query.filter(SpaceObject.classification == classification.upper())
    if search:
        query = query.filter(
            SpaceObject.name.ilike(f"%{search}%") |
            SpaceObject.catalog_number.ilike(f"%{search}%")
        )

    total  = query.count()
    offset = (page - 1) * size
    objs   = query.order_by(SpaceObject.updated_at.desc()).offset(offset).limit(size).all()
    pages  = (total + size - 1) // size

    data = [_serialize_space_object(o) for o in objs]

    return APIResponse(
        success=True,
        message=f"Orbital catalog — {total} objects tracked",
        data=data,
        pagination=PaginationSchema(page=page, size=size, total=total, pages=pages),
    )





@router.get("/objects/{catalog_number}", response_model=APIResponse[Dict[str, Any]])
def get_space_object(catalog_number: str, db: Session = Depends(get_db)):
    """Get a single space object by NORAD catalog number."""
    obj = db.query(SpaceObject).filter(SpaceObject.catalog_number == catalog_number).first()
    if not obj:
        
        obj = spacetrack_service.sync_by_catalog(db, catalog_number)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Object {catalog_number} not found in catalog or Space-Track")
    return APIResponse(success=True, message="Object retrieved", data=_serialize_space_object(obj))





@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
def get_catalog_stats(db: Session = Depends(get_db)):
    """Return catalog statistics."""
    stats = spacetrack_service.get_stats(db)
    return APIResponse(success=True, message="Catalog statistics", data=stats)





@router.post("/sync", response_model=APIResponse[Dict[str, Any]])
def trigger_sync(
    group: Optional[str] = Query(None, description="Space-Track group name (e.g. active, starlink, analyst). Omit for all."),
    limit: int = Query(500, ge=1, le=5000, description="Max records per group"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Manually trigger a Space-Track sync.
    Runs synchronously (returns after completion) for single groups,
    or queues as a background task for all groups.
    """
    if group:
        count = spacetrack_service.sync_group(db, group, limit=limit)
        return APIResponse(
            success=True,
            message=f"Synced group '{group}': {count} objects upserted",
            data={"group": group, "upserted": count},
        )

    
    def _bg_sync():
        from app.database.session import SessionLocal
        _db = SessionLocal()
        try:
            spacetrack_service.sync_all_groups(_db, limit_per_group=limit)
        finally:
            _db.close()

    if background_tasks:
        background_tasks.add_task(_bg_sync)
        return APIResponse(
            success=True,
            message="Full Space-Track sync queued in background",
            data={"groups": [g[0] for g in SYNC_GROUPS], "limit_per_group": limit},
        )

    
    results = spacetrack_service.sync_all_groups(db, limit_per_group=limit)
    return APIResponse(
        success=True,
        message="Full Space-Track sync completed",
        data=results,
    )





@router.get("/live", response_model=APIResponse[List[Dict[str, Any]]])
def fetch_live_from_spacetrack(
    group: str = Query("active", description="Space-Track group: active | starlink | analyst | ..."),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Pass-through: fetch live GP data directly from Space-Track (no DB write).
    Useful for frontend real-time views before the first DB sync completes.
    """
    records = spacetrack_service.fetch_group_json(group)[:limit]
    return APIResponse(
        success=True,
        message=f"Live Space-Track data for group '{group}' ({len(records)} records)",
        data=records,
    )





def _serialize_space_object(obj: SpaceObject) -> Dict[str, Any]:
    return {
        "id":             obj.id,
        "name":           obj.name,
        "catalog_number": obj.catalog_number,
        "cospar_id":      obj.cospar_id,
        "classification": obj.classification,
        "epoch":          obj.epoch.isoformat() if obj.epoch else None,
        "inclination":    obj.inclination,
        "eccentricity":   obj.eccentricity,
        "semimajor_axis": obj.semimajor_axis,
        "raan":           obj.raan,
        "arg_of_perigee": obj.arg_of_perigee,
        "mean_anomaly":   obj.mean_anomaly,
        "mean_motion":    obj.mean_motion,
        "period":         obj.period,
        "has_tle":        bool(obj.tle_line1 and obj.tle_line2),
        "updated_at":     obj.updated_at.isoformat() if obj.updated_at else None,
    }
