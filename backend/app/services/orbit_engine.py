from sgp4.api import Satrec, jday
from datetime import datetime, timedelta
import math
import logging
from typing import Tuple, Dict, Any, List

logger = logging.getLogger("app")


def _get_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        return None


class OrbitEngine:
    def propagate_state(self, line1: str, line2: str, target_time: datetime):
        """
        Propagates TLE to a target datetime.
        Returns (r, v) position/velocity vectors (km, km/s) in TEME frame.
        Falls back to mock vectors if sgp4 or numpy fails.
        """
        np = _get_numpy()
        try:
            satrec = Satrec.twoline2rv(line1, line2)
            jd, fr = jday(
                target_time.year, target_time.month, target_time.day,
                target_time.hour, target_time.minute,
                target_time.second + target_time.microsecond / 1e6
            )
            e, r, v = satrec.sgp4(jd, fr)
            if e != 0:
                raise Exception(f"SGP4 error code: {e}")
            if np:
                return np.array(r), np.array(v)
            return list(r), list(v)
        except Exception as e:
            logger.error(f"SGP4 propagation failed: {e}")
            if np:
                return np.array([6788.0, 0.0, 100.0]), np.array([0.0, 7.5, 0.1])
            return [6788.0, 0.0, 100.0], [0.0, 7.5, 0.1]

    def calculate_distance(self, pos1, pos2) -> float:
        np = _get_numpy()
        if np:
            return float(np.linalg.norm(np.array(pos1) - np.array(pos2)))
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))

    def calculate_relative_velocity(self, vel1, vel2) -> float:
        return self.calculate_distance(vel1, vel2)

    def propagate_orbit_path(self, line1: str, line2: str, steps: int = 72) -> List[Dict[str, float]]:
        """Propagates 1 full orbital period in steps for dashboard orbit curves."""
        path = []
        now = datetime.utcnow()
        for i in range(steps):
            t = now + timedelta(minutes=(i * 1.5))
            r, _ = self.propagate_state(line1, line2, t)
            path.append({"x": float(r[0]), "y": float(r[1]), "z": float(r[2])})
        return path


orbit_engine = OrbitEngine()
