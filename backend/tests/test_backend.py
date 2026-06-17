import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.orbit_engine import orbit_engine
from app.services.collision_engine import collision_engine
from app.services.risk_service import risk_analysis_service
import datetime
import numpy as np

client = TestClient(app)

def test_orbit_engine_distance():
    pos1 = np.array([1000.0, 0.0, 0.0])
    pos2 = np.array([1000.0, 3.0, 4.0])
    dist = orbit_engine.calculate_distance(pos1, pos2)
    assert dist == 5.0

def test_orbit_engine_relative_velocity():
    vel1 = np.array([7.5, 0.0, 0.0])
    vel2 = np.array([7.5, 1.0, 0.0])
    rel_vel = orbit_engine.calculate_relative_velocity(vel1, vel2)
    assert rel_vel == 1.0

def test_collision_engine_probability():
    # Large miss distance -> Low collision probability
    prob_low = collision_engine.calculate_probability(1000.0, 7.5)
    # Small miss distance -> High collision probability
    prob_high = collision_engine.calculate_probability(10.0, 7.5)
    assert prob_low < prob_high

def test_risk_analysis_ai():
    eval_result = risk_analysis_service.evaluate_risk({
        "miss_distance_m": 25.0,
        "relative_velocity_kms": 12.4,
        "space_weather_k_index": 5.0
    })
    assert "risk_level" in eval_result
    assert "ai_score" in eval_result
    assert eval_result["confidence"] >= 0.0

def test_api_dashboard_summary():
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    assert "tracked_satellites" in json_data["data"]

def test_api_invalid_route():
    resp = client.get("/api/v1/invalid-route")
    assert resp.status_code == 404
