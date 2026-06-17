from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.db_models import Satellite, SpaceObject, Telemetry, Maneuver, CollisionPrediction
from app.schemas.api_schemas import APIResponse, SatelliteResponse, PaginationSchema, ManeuverResponse, ManeuverCreate
from app.services.orbit_engine import orbit_engine
import datetime
from typing import List

router = APIRouter()

@router.get("", response_model=APIResponse[List[SatelliteResponse]])
def get_satellites(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    search: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Satellite).join(SpaceObject)
    
    if search:
        query = query.filter(SpaceObject.name.ilike(f"%{search}%") | SpaceObject.catalog_number.ilike(f"%{search}%"))
        
    total = query.count()
    offset = (page - 1) * size
    records = query.offset(offset).limit(size).all()
    
    pages = (total + size - 1) // size
    
    
    data = [SatelliteResponse.from_attributes(r) for r in records]
    
    return APIResponse(
        success=True,
        message="Satellite fleet records retrieved",
        data=data,
        pagination=PaginationSchema(page=page, size=size, total=total, pages=pages)
    )

@router.get("/{satellite_id}/telemetry", response_model=APIResponse[List[dict]])
def get_satellite_telemetry(satellite_id: int, db: Session = Depends(get_db)):
    sat = db.query(Satellite).filter(Satellite.id == satellite_id).first()
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")
        
    
    records = db.query(Telemetry).filter(Telemetry.satellite_id == satellite_id).order_by(Telemetry.timestamp.desc()).limit(50).all()
    data = []
    for r in records:
        data.append({
            "timestamp": r.timestamp.isoformat(),
            "altitude_km": r.altitude_km,
            "velocity_kms": r.velocity_kms,
            "temperature_c": r.temperature_c,
            "battery_charge": r.battery_charge,
            "neural_load": r.neural_load
        })
    return APIResponse(
        success=True,
        message="Telemetry log stream fetched",
        data=data
    )

@router.post("/maneuver", response_model=APIResponse[ManeuverResponse])
def execute_maneuver(maneuver_in: ManeuverCreate, db: Session = Depends(get_db)):
    sat = db.query(Satellite).filter(Satellite.id == maneuver_in.satellite_id).first()
    collision = db.query(CollisionPrediction).filter(CollisionPrediction.id == maneuver_in.collision_id).first()
    if not sat or not collision:
        raise HTTPException(status_code=404, detail="Entity references not found")

    
    fuel_g = float((abs(maneuver_in.delta_v_x) + abs(maneuver_in.delta_v_y) + abs(maneuver_in.delta_v_z)) * 33.3)
    
    maneuver = Maneuver(
        satellite_id=maneuver_in.satellite_id,
        collision_id=maneuver_in.collision_id,
        delta_v_x=maneuver_in.delta_v_x,
        delta_v_y=maneuver_in.delta_v_y,
        delta_v_z=maneuver_in.delta_v_z,
        fuel_cost_g=fuel_g,
        planned_time=maneuver_in.planned_time,
        status="EXECUTED"
    )
    db.add(maneuver)
    
    
    fuel_fraction = (fuel_g / 1000.0) / (sat.propellant_mass or 100.0)
    sat.fuel_percentage = max(0.0, sat.fuel_percentage - fuel_fraction * 100.0)
    
    
    collision.status = "MITIGATED"
    db.commit()
    db.refresh(maneuver)

    return APIResponse(
        success=True,
        message="Orbital maneuver delta-V path executed on satellite thrusters",
        data=ManeuverResponse.from_attributes(maneuver)
    )
