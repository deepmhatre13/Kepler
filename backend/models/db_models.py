"""
MongoDB Models Configuration
==============================
Redefines database model classes using our custom MongoDB BaseModel wrapper.
Exposes fields and properties to ensure full compatibility with SQLAlchemy-based queries,
preserving existing API serialization schemas and business logic.
"""

import datetime
from typing import Any, Dict, List, Optional
from database.session import BaseModel, Field, Relationship


class Organization(BaseModel):
    __tablename__ = "organizations"
    id = Field("id", "Organization")
    name = Field("name", "Organization")
    description = Field("description", "Organization")
    created_at = Field("created_at", "Organization")

    users = Relationship("User", "organization_id", uselist=True)
    satellites = Relationship("Satellite", "organization_id", uselist=True)


class Permission(BaseModel):
    __tablename__ = "permissions"
    id = Field("id", "Permission")
    name = Field("name", "Permission")
    description = Field("description", "Permission")


class Role(BaseModel):
    __tablename__ = "roles"
    id = Field("id", "Role")
    name = Field("name", "Role")
    description = Field("description", "Role")

    users = Relationship("User", "role_id", uselist=True)


class User(BaseModel):
    __tablename__ = "users"
    id = Field("id", "User")
    email = Field("email", "User")
    hashed_password = Field("hashed_password", "User")
    is_active = Field("is_active", "User")
    is_superuser = Field("is_superuser", "User")
    role_id = Field("role_id", "User")
    organization_id = Field("organization_id", "User")
    created_at = Field("created_at", "User")

    role = Relationship("Role", "role_id", uselist=False)
    organization = Relationship("Organization", "organization_id", uselist=False)
    notifications = Relationship("Notification", "user_id", uselist=True)
    audit_logs = Relationship("AuditLog", "user_id", uselist=True)


class SpaceObject(BaseModel):
    __tablename__ = "orbitalElements"
    id = Field("id", "SpaceObject")
    noradId = Field("noradId", "SpaceObject")
    objectName = Field("objectName", "SpaceObject")
    objectType = Field("objectType", "SpaceObject")
    cospar_id = Field("cospar_id", "SpaceObject")
    epoch = Field("epoch", "SpaceObject")
    inclination = Field("inclination", "SpaceObject")
    eccentricity = Field("eccentricity", "SpaceObject")
    semimajor_axis = Field("semimajor_axis", "SpaceObject")
    raan = Field("raan", "SpaceObject")
    arg_of_perigee = Field("arg_of_perigee", "SpaceObject")
    mean_anomaly = Field("mean_anomaly", "SpaceObject")
    mean_motion = Field("mean_motion", "SpaceObject")
    period = Field("period", "SpaceObject")
    tle_line1 = Field("tle_line1", "SpaceObject")
    tle_line2 = Field("tle_line2", "SpaceObject")
    updated_at = Field("updated_at", "SpaceObject")

    satellite_details = Relationship("Satellite", "space_object_id", uselist=False)
    debris_details = Relationship("Debris", "space_object_id", uselist=False)

    
    @property
    def catalog_number(self) -> str:
        return self.noradId

    @catalog_number.setter
    def catalog_number(self, val: str):
        self.noradId = val

    @property
    def name(self) -> str:
        return self.objectName

    @name.setter
    def name(self, val: str):
        self.objectName = val

    @property
    def classification(self) -> str:
        return self.objectType

    @classification.setter
    def classification(self, val: str):
        self.objectType = val


class Satellite(BaseModel):
    __tablename__ = "satellites"
    id = Field("id", "Satellite")
    noradId = Field("noradId", "Satellite")
    objectName = Field("objectName", "Satellite")
    objectType = Field("objectType", "Satellite")
    countryCode = Field("countryCode", "Satellite")
    launchDate = Field("launchDate", "Satellite")
    epoch = Field("epoch", "Satellite")
    inclination = Field("inclination", "Satellite")
    eccentricity = Field("eccentricity", "Satellite")
    meanMotion = Field("meanMotion", "Satellite")
    source = Field("source", "Satellite")
    createdAt = Field("createdAt", "Satellite")
    updatedAt = Field("updatedAt", "Satellite")

    
    space_object_id = Field("space_object_id", "Satellite")
    organization_id = Field("organization_id", "Satellite")
    status = Field("status", "Satellite")
    fuel_percentage = Field("fuel_percentage", "Satellite")
    dry_mass = Field("dry_mass", "Satellite")
    propellant_mass = Field("propellant_mass", "Satellite")
    operational_mode = Field("operational_mode", "Satellite")
    semimajor_axis = Field("semimajor_axis", "Satellite")
    period = Field("period", "Satellite")
    tle_line1 = Field("tle_line1", "Satellite")
    tle_line2 = Field("tle_line2", "Satellite")

    organization = Relationship("Organization", "organization_id", uselist=False)
    telemetry_records = Relationship("Telemetry", "satellite_id", uselist=True)
    maneuvers = Relationship("Maneuver", "satellite_id", uselist=True)

    @property
    def space_object(self) -> SpaceObject:
        """Dynamically construct SpaceObject for serialization from satellite properties."""
        return SpaceObject(
            id=self.space_object_id or self.id,
            noradId=self.noradId,
            objectName=self.objectName,
            objectType=self.objectType or "PAYLOAD",
            cospar_id=None,
            epoch=self.epoch,
            inclination=self.inclination,
            eccentricity=self.eccentricity,
            semimajor_axis=self.semimajor_axis,
            period=self.period,
            mean_motion=self.meanMotion,
            tle_line1=self.tle_line1,
            tle_line2=self.tle_line2,
        )


class Debris(BaseModel):
    __tablename__ = "debris"
    id = Field("id", "Debris")
    noradId = Field("noradId", "Debris")
    objectName = Field("objectName", "Debris")
    epoch = Field("epoch", "Debris")
    inclination = Field("inclination", "Debris")
    eccentricity = Field("eccentricity", "Debris")
    meanMotion = Field("meanMotion", "Debris")
    source = Field("source", "Debris")
    createdAt = Field("createdAt", "Debris")

    
    space_object_id = Field("space_object_id", "Debris")
    size_category = Field("size_category", "Debris")
    radar_cross_section = Field("radar_cross_section", "Debris")
    average_mass = Field("average_mass", "Debris")
    semimajor_axis = Field("semimajor_axis", "Debris")
    period = Field("period", "Debris")
    tle_line1 = Field("tle_line1", "Debris")
    tle_line2 = Field("tle_line2", "Debris")

    @property
    def space_object(self) -> SpaceObject:
        """Dynamically construct SpaceObject for serialization from debris properties."""
        return SpaceObject(
            id=self.space_object_id or self.id,
            noradId=self.noradId,
            objectName=self.objectName,
            objectType="DEBRIS",
            cospar_id=None,
            epoch=self.epoch,
            inclination=self.inclination,
            eccentricity=self.eccentricity,
            semimajor_axis=self.semimajor_axis,
            period=self.period,
            mean_motion=self.meanMotion,
            tle_line1=self.tle_line1,
            tle_line2=self.tle_line2,
        )


class Telemetry(BaseModel):
    __tablename__ = "telemetry"
    id = Field("id", "Telemetry")
    satellite_id = Field("satellite_id", "Telemetry")
    timestamp = Field("timestamp", "Telemetry")
    altitude_km = Field("altitude_km", "Telemetry")
    velocity_kms = Field("velocity_kms", "Telemetry")
    temperature_c = Field("temperature_c", "Telemetry")
    battery_charge = Field("battery_charge", "Telemetry")
    neural_load = Field("neural_load", "Telemetry")

    satellite = Relationship("Satellite", "satellite_id", uselist=False)


class OrbitalEvent(BaseModel):
    __tablename__ = "orbital_events"
    id = Field("id", "OrbitalEvent")
    event_type = Field("event_type", "OrbitalEvent")
    description = Field("description", "OrbitalEvent")
    recorded_at = Field("recorded_at", "OrbitalEvent")


class CollisionPrediction(BaseModel):
    __tablename__ = "conjunctions"
    id = Field("id", "CollisionPrediction")
    primaryObject = Field("primaryObject", "CollisionPrediction")
    secondaryObject = Field("secondaryObject", "CollisionPrediction")
    missDistance = Field("missDistance", "CollisionPrediction")
    riskScore = Field("riskScore", "CollisionPrediction")
    conjunctionTime = Field("conjunctionTime", "CollisionPrediction")
    createdAt = Field("createdAt", "CollisionPrediction")

    
    object_a_id = Field("object_a_id", "CollisionPrediction")
    object_b_id = Field("object_b_id", "CollisionPrediction")
    probability = Field("probability", "CollisionPrediction")
    tca = Field("tca", "CollisionPrediction")
    miss_distance_m = Field("miss_distance_m", "CollisionPrediction")
    relative_velocity_kms = Field("relative_velocity_kms", "CollisionPrediction")
    risk_level = Field("risk_level", "CollisionPrediction")
    status = Field("status", "CollisionPrediction")
    created_at = Field("created_at", "CollisionPrediction")

    risk_scores = Relationship("RiskScore", "collision_id", uselist=True)
    maneuvers = Relationship("Maneuver", "collision_id", uselist=True)

    @property
    def object_a(self) -> Optional[SpaceObject]:
        if not self.primaryObject:
            return None
        return self._session.query(SpaceObject).filter(SpaceObject.noradId == self.primaryObject).first()

    @property
    def object_b(self) -> Optional[SpaceObject]:
        if not self.secondaryObject:
            return None
        return self._session.query(SpaceObject).filter(SpaceObject.noradId == self.secondaryObject).first()

    @property
    def object_a_id(self) -> Optional[int]:
        oa = self.object_a
        return oa.id if oa else None

    @object_a_id.setter
    def object_a_id(self, val: int):
        self._data["object_a_id"] = val
        oa = self._session.query(SpaceObject).filter(SpaceObject.id == val).first()
        if oa:
            self.primaryObject = oa.catalog_number

    @property
    def object_b_id(self) -> Optional[int]:
        ob = self.object_b
        return ob.id if ob else None

    @object_b_id.setter
    def object_b_id(self, val: int):
        self._data["object_b_id"] = val
        ob = self._session.query(SpaceObject).filter(SpaceObject.id == val).first()
        if ob:
            self.secondaryObject = ob.catalog_number

    
    @property
    def probability(self) -> float:
        return self.riskScore or 0.0

    @probability.setter
    def probability(self, val: float):
        self.riskScore = val
        self._data["probability"] = val

    
    @property
    def miss_distance_m(self) -> float:
        return self.missDistance or 0.0

    @miss_distance_m.setter
    def miss_distance_m(self, val: float):
        self.missDistance = val
        self._data["miss_distance_m"] = val

    
    @property
    def tca(self) -> Optional[datetime.datetime]:
        return self.conjunctionTime

    @tca.setter
    def tca(self, val: datetime.datetime):
        self.conjunctionTime = val
        self._data["tca"] = val

    
    @property
    def created_at(self) -> Optional[datetime.datetime]:
        return self.createdAt

    @created_at.setter
    def created_at(self, val: datetime.datetime):
        self.createdAt = val
        self._data["created_at"] = val


class RiskScore(BaseModel):
    __tablename__ = "risk_scores"
    id = Field("id", "RiskScore")
    collision_id = Field("collision_id", "RiskScore")
    ai_score = Field("ai_score", "RiskScore")
    confidence = Field("confidence", "RiskScore")
    severity_classification = Field("severity_classification", "RiskScore")
    created_at = Field("created_at", "RiskScore")

    collision = Relationship("CollisionPrediction", "collision_id", uselist=False)


class Maneuver(BaseModel):
    __tablename__ = "maneuvers"
    id = Field("id", "Maneuver")
    satellite_id = Field("satellite_id", "Maneuver")
    collision_id = Field("collision_id", "Maneuver")
    delta_v_x = Field("delta_v_x", "Maneuver")
    delta_v_y = Field("delta_v_y", "Maneuver")
    delta_v_z = Field("delta_v_z", "Maneuver")
    fuel_cost_g = Field("fuel_cost_g", "Maneuver")
    planned_time = Field("planned_time", "Maneuver")
    status = Field("status", "Maneuver")
    created_at = Field("created_at", "Maneuver")

    satellite = Relationship("Satellite", "satellite_id", uselist=False)
    collision = Relationship("CollisionPrediction", "collision_id", uselist=False)


class Simulation(BaseModel):
    __tablename__ = "simulations"
    id = Field("id", "Simulation")
    name = Field("name", "Simulation")
    scenario_data = Field("scenario_data", "Simulation")
    results_data = Field("results_data", "Simulation")
    created_at = Field("created_at", "Simulation")


class SpaceWeather(BaseModel):
    __tablename__ = "spaceWeather"
    id = Field("id", "SpaceWeather")
    event_type = Field("event_type", "SpaceWeather")
    severity = Field("severity", "SpaceWeather")
    k_index = Field("k_index", "SpaceWeather")
    description = Field("description", "SpaceWeather")
    recorded_at = Field("recorded_at", "SpaceWeather")

    @property
    def eventTime(self) -> Optional[datetime.datetime]:
        return self.recorded_at

    @eventTime.setter
    def eventTime(self, val: datetime.datetime):
        self.recorded_at = val


class Alert(BaseModel):
    __tablename__ = "alerts"
    id = Field("id", "Alert")
    title = Field("title", "Alert")
    description = Field("description", "Alert")
    alert_type = Field("alert_type", "Alert")
    severity = Field("severity", "Alert")
    is_acknowledged = Field("is_acknowledged", "Alert")
    created_at = Field("created_at", "Alert")

    @property
    def createdAt(self) -> Optional[datetime.datetime]:
        return self.created_at

    @createdAt.setter
    def createdAt(self, val: datetime.datetime):
        self.created_at = val


class Notification(BaseModel):
    __tablename__ = "notifications"
    id = Field("id", "Notification")
    user_id = Field("user_id", "Notification")
    title = Field("title", "Notification")
    message = Field("message", "Notification")
    is_read = Field("is_read", "Notification")
    created_at = Field("created_at", "Notification")

    user = Relationship("User", "user_id", uselist=False)


class AgentRun(BaseModel):
    __tablename__ = "agent_runs"
    id = Field("id", "AgentRun")
    workflow_name = Field("workflow_name", "AgentRun")
    status = Field("status", "AgentRun")
    current_step = Field("current_step", "AgentRun")
    started_at = Field("started_at", "AgentRun")
    completed_at = Field("completed_at", "AgentRun")

    decisions = Relationship("AgentDecision", "agent_run_id", uselist=True)


class AgentDecision(BaseModel):
    __tablename__ = "agent_decisions"
    id = Field("id", "AgentDecision")
    agent_run_id = Field("agent_run_id", "AgentDecision")
    agent_name = Field("agent_name", "AgentDecision")
    action_taken = Field("action_taken", "AgentDecision")
    reasoning = Field("reasoning", "AgentDecision")
    decision_metadata = Field("decision_metadata", "AgentDecision")
    created_at = Field("created_at", "AgentDecision")

    agent_run = Relationship("AgentRun", "agent_run_id", uselist=False)


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    id = Field("id", "AuditLog")
    user_id = Field("user_id", "AuditLog")
    action = Field("action", "AuditLog")
    details = Field("details", "AuditLog")
    created_at = Field("created_at", "AuditLog")

    user = Relationship("User", "user_id", uselist=False)


class RocketBody(BaseModel):
    __tablename__ = "rocketBodies"
    id = Field("id", "RocketBody")
    noradId = Field("noradId", "RocketBody")
    objectName = Field("objectName", "RocketBody")
    epoch = Field("epoch", "RocketBody")
    inclination = Field("inclination", "RocketBody")
    eccentricity = Field("eccentricity", "RocketBody")
    meanMotion = Field("meanMotion", "RocketBody")
    source = Field("source", "RocketBody")
    createdAt = Field("createdAt", "RocketBody")


class SyncLog(BaseModel):
    __tablename__ = "syncLogs"
    id = Field("id", "SyncLog")
    syncType = Field("syncType", "SyncLog")
    status = Field("status", "SyncLog")
    recordsProcessed = Field("recordsProcessed", "SyncLog")
    createdAt = Field("createdAt", "SyncLog")
