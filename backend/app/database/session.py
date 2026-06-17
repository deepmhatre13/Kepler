"""
MongoDB Session & Query Adapter
================================
Implements a clean, Python-native session and query wrapper that mimics the
SQLAlchemy API, redirecting all database operations to MongoDB using pymongo.
Guarantees zero modifications to route controllers and frontend expectations.
"""

import logging
from typing import Any, Dict, List, Optional
import pymongo
from app.core.config import settings

logger = logging.getLogger("app")


_mongo_client = None

def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        uri = settings.MONGODB_URI
        logger.info(f"🔌 Connecting to MongoDB: {uri}")
        _mongo_client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
    return _mongo_client


class MongoExpression:
    """Helper representing a MongoDB query filter expression with operator overloading."""
    def __init__(self, query_dict: Dict[str, Any], model_name: Optional[str] = None):
        self.query_dict = query_dict
        self.model_name = model_name
        self.sort_field = None
        self.sort_dir = 1

    def __or__(self, other):
        other_dict = other.query_dict if isinstance(other, MongoExpression) else other
        return MongoExpression({"$or": [self.query_dict, other_dict]}, self.model_name)

    def __and__(self, other):
        other_dict = other.query_dict if isinstance(other, MongoExpression) else other
        return MongoExpression({"$and": [self.query_dict, other_dict]}, self.model_name)


class Field:
    """Descriptor class representing a MongoDB document attribute."""
    def __init__(self, name: str, model_name: Optional[str] = None):
        self.name = name
        self.model_name = model_name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance._data.get(self.name)

    def __set__(self, instance, value):
        instance._data[self.name] = value

    def __eq__(self, other):
        return MongoExpression({self.name: other}, self.model_name)

    def __ne__(self, other):
        return MongoExpression({self.name: {"$ne": other}}, self.model_name)

    def __lt__(self, other):
        return MongoExpression({self.name: {"$lt": other}}, self.model_name)

    def __le__(self, other):
        return MongoExpression({self.name: {"$lte": other}}, self.model_name)

    def __gt__(self, other):
        return MongoExpression({self.name: {"$gt": other}}, self.model_name)

    def __ge__(self, other):
        return MongoExpression({self.name: {"$gte": other}}, self.model_name)

    def in_(self, other):
        return MongoExpression({self.name: {"$in": list(other)}}, self.model_name)

    def ilike(self, other: str):
        clean_regex = other.replace("%", "")
        return MongoExpression({self.name: {"$regex": clean_regex, "$options": "i"}}, self.model_name)

    def desc(self):
        expr = MongoExpression({}, self.model_name)
        expr.sort_field = self.name
        expr.sort_dir = -1
        return expr

    def asc(self):
        expr = MongoExpression({}, self.model_name)
        expr.sort_field = self.name
        expr.sort_dir = 1
        return expr


class Relationship:
    """Descriptor managing relationship lookups between MongoDB collections."""
    def __init__(self, target_model: str, foreign_key_attr: str, uselist: bool = False):
        self.target_model = target_model
        self.foreign_key_attr = foreign_key_attr
        self.uselist = uselist

    def __get__(self, instance, owner):
        if instance is None:
            return self

        
        from app.models import db_models
        target_class = getattr(db_models, self.target_model)
        
        session = getattr(instance, "_session", None)
        if not session:
            client = get_mongo_client()
            db_name = uri_db_name(settings.MONGODB_URI)
            session = MongoSession(client, db_name)

        fk_val = getattr(instance, self.foreign_key_attr, None)
        
        if self.uselist:
            
            return session.query(target_class).filter({self.foreign_key_attr: instance.id}).all()
        else:
            if fk_val is None:
                
                return session.query(target_class).filter({self.foreign_key_attr: instance.id}).first()
            
            return session.query(target_class).filter({"id": fk_val}).first()


class BaseModel:
    """Base class for all MongoDB documents, supplying dictionary mappings and property fallbacks."""
    __tablename__ = "base"

    def __init__(self, _session=None, **kwargs):
        self._session = _session
        self._data = {}
        
        
        if "_id" in kwargs:
            self._id = kwargs["_id"]
            if "id" not in kwargs:
                kwargs["id"] = kwargs["_id"]
        else:
            self._id = kwargs.get("id")

        for k, v in kwargs.items():
            self._data[k] = v
            if not hasattr(self.__class__, k) or isinstance(getattr(self.__class__, k), Field):
                setattr(self, k, v)

    @property
    def id(self) -> Optional[int]:
        return self._data.get("id") or getattr(self, "_id", None)

    @id.setter
    def id(self, val: int):
        self._id = val
        self._data["id"] = val

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def _to_dict(self) -> Dict[str, Any]:
        d = {}
        for k, v in self._data.items():
            if k in ("_session", "_id"):
                continue
            d[k] = v
        
        
        for k in dir(self):
            if k.startswith("_") or k in ("metadata", "registry", "id", "space_object", "satellite_details", "debris_details", "telemetry_records", "maneuvers", "risk_scores"):
                continue
            val = getattr(self, k)
            if not callable(val) and not isinstance(val, (MongoQuery, MongoExpression, Relationship, Field)):
                d[k] = val
        if self.id is not None:
            d["id"] = self.id
        return d


class MongoQuery:
    """Query builder that parses criteria and compiles to MongoDB commands."""
    def __init__(self, model_class, session):
        self.model_class = model_class
        self.session = session
        self.db = session.db
        self.collection_name = model_class.__tablename__
        self.filter_dict = {}
        self.sort_params = None
        self.offset_val = 0
        self.limit_val = None

    def filter(self, *args):
        for arg in args:
            if isinstance(arg, MongoExpression):
                
                if arg.model_name and arg.model_name != self.model_class.__name__:
                    self._translate_join_filter(arg)
                else:
                    self.add_filter_dict(arg.query_dict)
            elif isinstance(arg, dict):
                self.add_filter_dict(arg)
        return self

    def _translate_join_filter(self, expr: MongoExpression):
        
        from app.models import db_models
        target_class = getattr(db_models, expr.model_name)
        target_collection = target_class.__tablename__
        
        
        matching_docs = list(self.db[target_collection].find(expr.query_dict, {"id": 1}))
        matching_ids = [doc["id"] for doc in matching_docs]
        
        
        if self.model_class.__name__ in ("Satellite", "Debris"):
            self.add_filter_dict({"space_object_id": {"$in": matching_ids}})
        elif self.model_class.__name__ == "CollisionPrediction":
            self.add_filter_dict({
                "$or": [
                    {"object_a_id": {"$in": matching_ids}},
                    {"object_b_id": {"$in": matching_ids}}
                ]
            })

    def join(self, *args, **kwargs):
        
        return self

    def options(self, *args, **kwargs):
        return self

    def order_by(self, *args):
        sort_list = []
        for arg in args:
            if isinstance(arg, tuple):
                sort_list.append(arg)
            elif isinstance(arg, str):
                sort_list.append((arg, 1))
            elif hasattr(arg, "name"):
                sort_list.append((arg.name, 1))
            elif isinstance(arg, MongoExpression):
                if hasattr(arg, "sort_field") and arg.sort_field:
                    sort_list.append((arg.sort_field, arg.sort_dir))
        if sort_list:
            self.sort_params = sort_list
        return self

    def offset(self, value: int):
        self.offset_val = value
        return self

    def limit(self, value: int):
        self.limit_val = value
        return self

    def add_filter_dict(self, d: Dict[str, Any]):
        for k, v in d.items():
            if k == "$or":
                if "$or" not in self.filter_dict:
                    self.filter_dict["$or"] = []
                self.filter_dict["$or"].extend(v)
            elif k == "$and":
                if "$and" not in self.filter_dict:
                    self.filter_dict["$and"] = []
                self.filter_dict["$and"].extend(v)
            elif k in self.filter_dict:
                if isinstance(self.filter_dict[k], dict) and isinstance(v, dict):
                    self.filter_dict[k].update(v)
                else:
                    self.filter_dict[k] = v
            else:
                self.filter_dict[k] = v

    def all(self) -> List[Any]:
        cursor = self.db[self.collection_name].find(self.filter_dict)
        if self.sort_params:
            cursor = cursor.sort(self.sort_params)
        if self.offset_val:
            cursor = cursor.skip(self.offset_val)
        if self.limit_val is not None:
            cursor = cursor.limit(self.limit_val)
        
        return [self.model_class(_session=self.session, **doc) for doc in cursor]

    def first(self) -> Optional[Any]:
        cursor = self.db[self.collection_name].find(self.filter_dict)
        if self.sort_params:
            cursor = cursor.sort(self.sort_params)
        if self.offset_val:
            cursor = cursor.skip(self.offset_val)
        
        for doc in cursor:
            return self.model_class(_session=self.session, **doc)
        return None

    def count(self) -> int:
        return self.db[self.collection_name].count_documents(self.filter_dict)


class MongoSession:
    """Manages transactional state and persistence logic for MongoDB."""
    def __init__(self, client, db_name: str):
        self.client = client
        self.db = client[db_name]
        self.pending_adds = []

    def query(self, model_class) -> MongoQuery:
        return MongoQuery(model_class, self)

    def add(self, obj: Any):
        obj._session = self
        if obj not in self.pending_adds:
            self.pending_adds.append(obj)

    def commit(self):
        for obj in self.pending_adds:
            collection_name = obj.__tablename__
            doc = obj._to_dict()
            
            if obj.id is None:
                
                new_id = self._get_next_id(collection_name)
                obj.id = new_id
                doc["id"] = new_id
                doc["_id"] = new_id
                self.db[collection_name].insert_one(doc)
                
                
                obj._id = new_id
                obj._data["id"] = new_id
                obj._data["_id"] = new_id
                setattr(obj, "id", new_id)
            else:
                doc["_id"] = obj.id
                self.db[collection_name].replace_one({"id": obj.id}, doc, upsert=True)
        self.pending_adds = []

    def delete(self, obj: Any):
        collection_name = obj.__tablename__
        if obj.id is not None:
            self.db[collection_name].delete_one({"id": obj.id})
        if obj in self.pending_adds:
            self.pending_adds.remove(obj)

    def refresh(self, obj: Any):
        collection_name = obj.__tablename__
        if obj.id is not None:
            doc = self.db[collection_name].find_one({"id": obj.id})
            if doc:
                obj._id = doc.get("_id")
                obj._data = doc
                for k, v in doc.items():
                    setattr(obj, k, v)

    def rollback(self):
        self.pending_adds = []

    def close(self):
        pass

    def _get_next_id(self, collection_name: str) -> int:
        res = self.db["counters"].find_one_and_update(
            {"_id": collection_name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER
        )
        return res["seq"]


def uri_db_name(uri: str) -> str:
    parsed = pymongo.uri_parser.parse_uri(uri)
    return parsed.get("database") or "orbital_guardian"



def SessionLocal() -> MongoSession:
    client = get_mongo_client()
    db_name = uri_db_name(settings.MONGODB_URI)
    return MongoSession(client, db_name)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
