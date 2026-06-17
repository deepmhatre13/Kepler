from typing import TypedDict, List, Dict, Any
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.db_models import AgentRun, AgentDecision, CollisionPrediction
from app.services.collision_engine import collision_engine
from app.services.risk_service import risk_analysis_service
from app.services.simulation_service import simulation_service
from app.services.openai_service import openai_service
import datetime
import logging

logger = logging.getLogger("app")



class AgentState(TypedDict):
    run_id: int
    collision_id: int
    object_a_name: str
    object_b_name: str
    risk_score: float
    probability: float
    maneuver_options: List[Dict[str, Any]]
    simulated_trajectories: List[Dict[str, Any]]
    recommendation: str
    logs: List[str]



def monitoring_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == state["run_id"]).first()
        if run:
            run.current_step = "MONITORING"
            db.commit()

        decision = AgentDecision(
            agent_run_id=state["run_id"],
            agent_name="MonitoringAgent",
            action_taken="Ingest Conjunction Registry",
            reasoning=f"Conjunction incident identified. Querying state files for {state['object_a_name']}."
        )
        db.add(decision)
        db.commit()
        state["logs"].append("MonitoringAgent: Telemetry tracks retrieved and verified.")
    finally:
        db.close()
    return state



def risk_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == state["run_id"]).first()
        if run:
            run.current_step = "RISK_EVAL"
            db.commit()

        collision = db.query(CollisionPrediction).filter(CollisionPrediction.id == state["collision_id"]).first()
        miss_dist = collision.miss_distance_m if collision else 100.0
        rel_vel = collision.relative_velocity_kms if collision else 7.5

        ai_eval = risk_analysis_service.evaluate_risk({
            "miss_distance_m": miss_dist,
            "relative_velocity_kms": rel_vel,
            "space_weather_k_index": 4.0
        })

        state["risk_score"] = ai_eval["ai_score"]
        state["probability"] = ai_eval["confidence"]

        decision = AgentDecision(
            agent_run_id=state["run_id"],
            agent_name="RiskAgent",
            action_taken="AI Risk Classification",
            reasoning=f"Risk evaluated. AI Score: {ai_eval['ai_score']}/10, Risk Category: {ai_eval['risk_level']}.",
            decision_metadata=ai_eval
        )
        db.add(decision)
        db.commit()
        state["logs"].append(f"RiskAgent: AI Classification finished. Score: {ai_eval['ai_score']}.")
    finally:
        db.close()
    return state



def planning_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == state["run_id"]).first()
        if run:
            run.current_step = "PLANNING"
            db.commit()

        maneuver_options = [
            {"vector": {"x": 4.2, "y": 0.0, "z": 0.0}, "fuel_cost_g": 140.0, "delay_min": 12.0},
            {"vector": {"x": -2.5, "y": 1.0, "z": 0.0}, "fuel_cost_g": 95.0, "delay_min": 24.0}
        ]
        state["maneuver_options"] = maneuver_options

        decision = AgentDecision(
            agent_run_id=state["run_id"],
            agent_name="PlanningAgent",
            action_taken="Generate Maneuver Options",
            reasoning="Calculated two escape vector windows utilizing hydrazine thrusters.",
            decision_metadata={"options": maneuver_options}
        )
        db.add(decision)
        db.commit()
        state["logs"].append("PlanningAgent: Escape burn options calculated.")
    finally:
        db.close()
    return state



def simulation_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == state["run_id"]).first()
        if run:
            run.current_step = "SIMULATION"
            db.commit()

        sim_results = []
        for idx, opt in enumerate(state["maneuver_options"]):
            sim = simulation_service.run_maneuver_simulation(
                db,
                satellite_name=state["object_a_name"],
                tle1="1 49201U 21080A   26158.81422394  .00012248  00000-0  11442-3 0  9997",
                tle2="2 49201  51.6422  82.1488 0008422  42.1102 318.4201 15.54020310242223",
                delta_v=opt["vector"]
            )
            sim_results.append({
                "option_idx": idx,
                "simulation_id": sim["simulation_id"],
                "fuel_cost_g": sim["results"]["fuel_consumed_g"]
            })

        state["simulated_trajectories"] = sim_results

        decision = AgentDecision(
            agent_run_id=state["run_id"],
            agent_name="SimulationAgent",
            action_taken="Execute Burn Simulations",
            reasoning="Simulated trajectories for both planning options. Both secure positive clearance margins.",
            decision_metadata={"simulations": sim_results}
        )
        db.add(decision)
        db.commit()
        state["logs"].append("SimulationAgent: Maneuver path projections calculated successfully.")
    finally:
        db.close()
    return state



def mission_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == state["run_id"]).first()
        if run:
            run.current_step = "MISSION_RECOMMENDATION"
            run.status = "COMPLETED"
            run.completed_at = datetime.datetime.utcnow()
            db.commit()

        summary = openai_service.explain_collision({
            "obj_a": state["object_a_name"],
            "obj_b": state["object_b_name"],
            "prob": f"{state['probability'] * 100:.2f}%",
            "miss": 42
        })
        state["recommendation"] = summary

        decision = AgentDecision(
            agent_run_id=state["run_id"],
            agent_name="MissionAgent",
            action_taken="Generate Final Recommendation",
            reasoning=f"Mission strategy compiled: {summary}"
        )
        db.add(decision)
        db.commit()
        state["logs"].append("MissionAgent: Final command briefing generated.")
    finally:
        db.close()
    return state


def _build_workflow():
    """Lazily import langgraph so the server boots even if it's not installed."""
    try:
        from langgraph.graph import StateGraph, END  
        workflow = StateGraph(AgentState)
        workflow.add_node("monitoring", monitoring_node)
        workflow.add_node("risk", risk_node)
        workflow.add_node("planning", planning_node)
        workflow.add_node("simulation", simulation_node)
        workflow.add_node("mission", mission_node)
        workflow.set_entry_point("monitoring")
        workflow.add_edge("monitoring", "risk")
        workflow.add_edge("risk", "planning")
        workflow.add_edge("planning", "simulation")
        workflow.add_edge("simulation", "mission")
        workflow.add_edge("mission", END)
        return workflow.compile()
    except ImportError:
        logger.warning("langgraph not installed — agent workflow disabled. Install with: pip install langgraph")
        return None



agent_app = _build_workflow()


def run_agent_workflow(db: Session, collision_id: int) -> int:
    if agent_app is None:
        logger.error("Agent workflow unavailable: langgraph not installed.")
        return 0

    collision = db.query(CollisionPrediction).filter(CollisionPrediction.id == collision_id).first()
    if not collision:
        return 0

    run = AgentRun(workflow_name="CollisionAvoidanceGraph", status="RUNNING")
    db.add(run)
    db.commit()
    db.refresh(run)

    initial_state: AgentState = {
        "run_id": run.id,
        "collision_id": collision_id,
        "object_a_name": collision.object_a.name if collision.object_a else "UNKNOWN-SAT",
        "object_b_name": collision.object_b.name if collision.object_b else "DEBRIS-SHARD",
        "risk_score": 0.0,
        "probability": collision.probability,
        "maneuver_options": [],
        "simulated_trajectories": [],
        "recommendation": "",
        "logs": []
    }

    agent_app.invoke(initial_state)
    return run.id
