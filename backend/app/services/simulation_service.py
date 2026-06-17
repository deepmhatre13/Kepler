from sqlalchemy.orm import Session
from app.models.db_models import Simulation
from app.services.orbit_engine import orbit_engine
import datetime
import math
import logging
from typing import Dict, Any

logger = logging.getLogger("app")


def _vec_norm(v: Dict[str, float]) -> float:
    return math.sqrt(v.get("x", 0.0) ** 2 + v.get("y", 0.0) ** 2 + v.get("z", 0.0) ** 2)


def _vec_add(vec_list, delta: Dict[str, float]):
    """Add delta_v dict to a position/velocity list/array."""
    try:
        
        return [
            vec_list[0] + delta.get("x", 0.0) / 1000.0,
            vec_list[1] + delta.get("y", 0.0) / 1000.0,
            vec_list[2] + delta.get("z", 0.0) / 1000.0,
        ]
    except Exception:
        return vec_list


class SimulationService:
    def run_maneuver_simulation(
        self,
        db: Session,
        satellite_name: str,
        tle1: str,
        tle2: str,
        delta_v: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Simulates the orbit path trajectory after applying a delta-V vector burn.
        """
        now = datetime.datetime.utcnow()
        r_init, v_init = orbit_engine.propagate_state(tle1, tle2, now)

        trajectory_points = []
        for step in range(36):
            t = now + datetime.timedelta(minutes=(step * 3.0))
            r_step, _ = orbit_engine.propagate_state(tle1, tle2, t)
            drift_scale = (step ** 2) * 0.01 / 1000.0
            r_simulated = [
                float(r_step[0]) + drift_scale * delta_v.get("x", 0.0),
                float(r_step[1]) + drift_scale * delta_v.get("y", 0.0),
                float(r_step[2]) + drift_scale * delta_v.get("z", 0.0),
            ]
            trajectory_points.append({"x": r_simulated[0], "y": r_simulated[1], "z": r_simulated[2]})

        fuel_consumed_g = _vec_norm(delta_v) * 33.3

        scenario_data: Dict[str, Any] = {
            "satellite_name": satellite_name,
            "delta_v": delta_v,
            "timestamp": now.isoformat()
        }
        results_data: Dict[str, Any] = {
            "initial_position": [float(r_init[0]), float(r_init[1]), float(r_init[2])],
            "trajectory": trajectory_points,
            "fuel_consumed_g": fuel_consumed_g
        }

        sim = Simulation(
            name=f"BURN_SIM_{satellite_name.upper()}_{now.strftime('%H%M%S')}",
            scenario_data=scenario_data,
            results_data=results_data
        )
        db.add(sim)
        db.commit()
        db.refresh(sim)

        return {
            "simulation_id": sim.id,
            "name": sim.name,
            "results": results_data
        }


simulation_service = SimulationService()
