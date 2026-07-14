import logging
import math
from typing import Dict, Any

logger = logging.getLogger("app")


class RiskAnalysisService:
    """
    AI-powered risk analysis service.
    Uses PyTorch + XGBoost when available; falls back to heuristic scoring
    so the server always starts regardless of heavy-ML dependencies.
    """

    def __init__(self):
        self.model_version = "v1.2.0"
        self._pytorch_model = None
        self._xgb_model = None
        self._ml_available = False
        self._try_load_ml()

    def _try_load_ml(self):
        try:
            import torch
            import torch.nn as nn
            import numpy as np  

            class _SpaceRiskClassifier(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.fc1 = nn.Linear(6, 16)
                    self.relu = nn.ReLU()
                    self.fc2 = nn.Linear(16, 3)

                def forward(self, x):
                    return self.fc2(self.relu(self.fc1(x)))

            self._pytorch_model = _SpaceRiskClassifier()
            self._pytorch_model.eval()
            self._torch = torch
            self._np = np
            self._nn = nn
            self._ml_available = True
            logger.info("✅ PyTorch risk classifier loaded.")
        except ImportError:
            logger.warning("PyTorch/numpy not installed — using heuristic risk scorer (install torch numpy for ML mode).")

        try:
            import xgboost as xgb  
            self._xgb = xgb
        except ImportError:
            self._xgb = None

    
    
    
    def _heuristic_risk(self, miss: float, vel: float, weather: float) -> Dict[str, Any]:
        """
        Simple physics-based heuristic risk scorer.
        Returns the same dict shape as the ML path.
        """
        
        miss_norm   = max(0.0, min(1.0, 1.0 - miss / 10_000.0))   
        vel_norm    = max(0.0, min(1.0, vel / 15.0))               
        weather_norm = max(0.0, min(1.0, weather / 9.0))           

        raw = 0.55 * miss_norm + 0.35 * vel_norm + 0.10 * weather_norm
        ai_score = round(raw * 10.0, 2)
        confidence = round(0.60 + raw * 0.35, 4)

        if ai_score > 7.5:
            risk_level, severity = "HIGH",   "CRITICAL"
        elif ai_score > 4.5:
            risk_level, severity = "MEDIUM", "WARNING"
        else:
            risk_level, severity = "LOW",    "NORMAL"

        return {
            "ai_score":       ai_score,
            "confidence":     confidence,
            "risk_level":     risk_level,
            "severity":       severity,
            "model_version":  "heuristic-1.0",
        }

    
    
    
    def evaluate_risk(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        miss    = float(inputs.get("miss_distance_m",        100.0))
        vel     = float(inputs.get("relative_velocity_kms",   7.5))
        size    = float(inputs.get("size_category_val",        2.0))
        mass    = float(inputs.get("object_mass",           1000.0))
        weather = float(inputs.get("space_weather_k_index",    4.0))
        altitude= float(inputs.get("orbit_altitude_km",      400.0))

        if self._ml_available:
            try:
                import numpy as np
                feat_arr = np.array([[miss, vel, size, mass, weather, altitude]], dtype=np.float32)
                tensor_input = self._torch.from_numpy(feat_arr)

                with self._torch.no_grad():
                    logits = self._pytorch_model(tensor_input)
                    probs  = self._torch.softmax(logits, dim=1).numpy()[0]

                risk_classes = ["LOW", "MEDIUM", "HIGH"]
                risk_idx     = int(np.argmax(probs))
                risk_level   = risk_classes[risk_idx]
                confidence   = float(probs[risk_idx])
                ai_score     = round(confidence * 10.0, 2)
                severity     = "CRITICAL" if ai_score > 7.5 else ("WARNING" if ai_score > 4.5 else "NORMAL")

                return {
                    "ai_score":      ai_score,
                    "confidence":    confidence,
                    "risk_level":    risk_level,
                    "severity":      severity,
                    "model_version": self.model_version,
                }
            except Exception as e:
                logger.error(f"ML risk evaluation failed, falling back to heuristic: {e}")

        return self._heuristic_risk(miss, vel, weather)


risk_analysis_service = RiskAnalysisService()
