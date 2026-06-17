from sqlalchemy.orm import Session
from app.models.db_models import SpaceObject, CollisionPrediction
from app.services.orbit_engine import orbit_engine
import datetime
import math
import logging
from typing import Dict, Any, List

logger = logging.getLogger("app")


class CollisionEngine:
    def calculate_probability(self, miss_distance_m: float, rel_vel_kms: float, r_combined_m: float = 15.0) -> float:
        """
        Calculates collision probability based on a simplified 2D Gaussian error distribution.
        """
        try:
            sigma = max(20.0, miss_distance_m * 0.4)
            prob = math.exp(-0.5 * (miss_distance_m ** 2) / (sigma ** 2)) * (r_combined_m ** 2) / (2 * sigma ** 2)
            return min(0.95, max(0.0001, prob))
        except Exception as e:
            logger.error(f"Error calculating probability: {e}")
            return 0.001

    def predict_collisions(self, db: Session, lookahead_hours: float = 24.0) -> List[CollisionPrediction]:
        """
        Polls active TLE catalog, propagates object coordinates, and inserts conjunction alerts.
        """
        objects = db.query(SpaceObject).filter(
            SpaceObject.tle_line1 != None,
            SpaceObject.tle_line2 != None
        ).all()

        predictions = []
        now = datetime.datetime.utcnow()

        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                obj_a = objects[i]
                obj_b = objects[j]
                try:
                    r_a, v_a = orbit_engine.propagate_state(obj_a.tle_line1, obj_a.tle_line2, now)
                    r_b, v_b = orbit_engine.propagate_state(obj_b.tle_line1, obj_b.tle_line2, now)

                    distance_km = orbit_engine.calculate_distance(r_a, r_b)

                    if distance_km < 15.0:
                        miss_m  = distance_km * 1000.0
                        rel_vel = orbit_engine.calculate_relative_velocity(v_a, v_b)
                        prob    = self.calculate_probability(miss_m, rel_vel)

                        if prob > 0.05:
                            risk_level = "CRITICAL"
                        elif prob > 0.01:
                            risk_level = "HIGH"
                        elif prob > 0.001:
                            risk_level = "MEDIUM"
                        else:
                            risk_level = "LOW"

                        pred = CollisionPrediction(
                            object_a_id=obj_a.id,
                            object_b_id=obj_b.id,
                            probability=prob,
                            tca=now + datetime.timedelta(minutes=12.0),
                            miss_distance_m=miss_m,
                            relative_velocity_kms=rel_vel,
                            risk_level=risk_level,
                            status="PENDING"
                        )
                        db.add(pred)
                        predictions.append(pred)
                except Exception as e:
                    logger.warning(
                        f"Failed to calculate intersection between "
                        f"{obj_a.catalog_number} and {obj_b.catalog_number}: {e}"
                    )

        db.commit()
        return predictions


collision_engine = CollisionEngine()
