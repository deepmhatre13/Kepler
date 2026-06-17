from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.db_models import AgentRun, AgentDecision, CollisionPrediction
from app.schemas.api_schemas import APIResponse, AgentRunResponse, PaginationSchema
from app.agents.workflow import run_agent_workflow
from typing import List

router = APIRouter()

@router.post("/trigger/{collision_id}", response_model=APIResponse[dict])
def trigger_agent_mitigation_workflow(collision_id: int, db: Session = Depends(get_db)):
    collision = db.query(CollisionPrediction).filter(CollisionPrediction.id == collision_id).first()
    if not collision:
        raise HTTPException(status_code=404, detail="Collision conjunction not found")
        
    run_id = run_agent_workflow(db, collision_id)
    return APIResponse(
        success=True,
        message="LangGraph collision avoidance agent workflow triggered",
        data={"run_id": run_id, "status": "RUNNING"}
    )

@router.get("/runs", response_model=APIResponse[List[AgentRunResponse]])
def get_agent_runs(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1),
    db: Session = Depends(get_db)
):
    query = db.query(AgentRun).order_by(AgentRun.started_at.desc())
    total = query.count()
    offset = (page - 1) * size
    records = query.offset(offset).limit(size).all()
    pages = (total + size - 1) // size
    
    data = [AgentRunResponse.from_attributes(r) for r in records]
    
    return APIResponse(
        success=True,
        message="Agent run registry logs fetched",
        data=data,
        pagination=PaginationSchema(page=page, size=size, total=total, pages=pages)
    )

@router.get("/runs/{run_id}", response_model=APIResponse[AgentRunResponse])
def get_agent_run_details(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Agent run profile not found")
    return APIResponse(
        success=True,
        message="Agent run telemetry retrieved",
        data=AgentRunResponse.from_attributes(run)
    )
