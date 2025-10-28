from contextlib import contextmanager
import os
import json
from typing import Generator, Optional, List, Dict

from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False)

RATE_CARD_TABLE = "rate_card"
SOW_KB_TABLE = "sow_kb"

class RateCardModel(Base):
    __tablename__ = RATE_CARD_TABLE
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, unique=True, nullable=False)
    rate = Column(Float, nullable=False)

class SowKBModel(Base):
    __tablename__ = SOW_KB_TABLE
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    features_json = Column(Text)  # JSON text
    final_price = Column(Float)
    metadata_json = Column(Text)

def get_engine(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    return engine

def init_db(db_path: str = "data.sqlite") -> None:
    """
    Ensure the sqlite DB file exists, create tables and seed canonical rate card if empty.
    """
    if not os.path.exists(db_path):
        open(db_path, "a").close()

    engine = get_engine(db_path)
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed canonical rate card if table empty
    session = SessionLocal()
    try:
        count = session.query(RateCardModel).count()
        if count == 0:
            DEFAULT_RATE_CARD = {
                "Software Developer": 80.0,
                "Senior Software Developer": 120.0,
                "Software Architect": 150.0,
                "WordPress Developer": 70.0,
                "Project Manager": 95.0,
                "Cloud Architect / DevOps Engineer": 140.0
            }
            for role, rate in DEFAULT_RATE_CARD.items():
                session.add(RateCardModel(role=role, rate=float(rate)))
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

# DEFAULT rate card limited to requested roles
DEFAULT_RATE_CARD: Dict[str, float] = {
    "Software Developer": 80.0,
    "Senior Software Developer": 120.0,
    "Software Architect": 150.0,
    "WordPress Developer": 70.0,
    "Project Manager": 95.0,
    "Cloud Architect / DevOps Engineer": 140.0
}

class RateCardStore:
    def __init__(self, db_path: str = "data.sqlite"):
        self.db_path = db_path
        self.engine = get_engine(db_path)
        try:
            SessionLocal.configure(bind=self.engine)
        except Exception:
            pass

    def get_rate_card(self) -> Dict[str, float]:
        session = SessionLocal()
        try:
            rows = session.query(RateCardModel).all()
            if not rows:
                return DEFAULT_RATE_CARD.copy()
            return {r.role: r.rate for r in rows}
        finally:
            session.close()

    def update_rate_card(self, new_card: Dict[str, float]):
        session = SessionLocal()
        try:
            # Upsert provided roles
            for role, rate in new_card.items():
                existing = session.query(RateCardModel).filter_by(role=role).first()
                if existing:
                    existing.rate = float(rate)
                else:
                    session.add(RateCardModel(role=role, rate=float(rate)))
            # Remove roles not present in new_card
            existing_roles = {r.role for r in session.query(RateCardModel).all()}
            to_delete = existing_roles - set(new_card.keys())
            if to_delete:
                session.query(RateCardModel).filter(RateCardModel.role.in_(list(to_delete))).delete(synchronize_session=False)
            session.commit()
        finally:
            session.close()

class SowKnowledgeStore:
    def __init__(self, db_path: str = "data.sqlite"):
        self.db_path = db_path
        self.engine = get_engine(db_path)
        try:
            SessionLocal.configure(bind=self.engine)
        except Exception:
            pass

    def insert(self, parsed: dict, metadata: dict):
        session = SessionLocal()
        try:
            model = SowKBModel(
                filename=metadata.get("name") or metadata.get("path_lower"),
                features_json=json.dumps(parsed.get("features", [])),
                final_price=float(parsed.get("final_price") or 0.0),
                metadata_json=json.dumps(metadata)
            )
            session.add(model)
            session.commit()
            return model.id
        finally:
            session.close()

    def get_all(self) -> List[Dict]:
        session = SessionLocal()
        try:
            rows = session.query(SowKBModel).all()
            out = []
            for r in rows:
                out.append({
                    "id": r.id,
                    "filename": r.filename,
                    "features": json.loads(r.features_json) if r.features_json else [],
                    "final_price": r.final_price,
                    "metadata": json.loads(r.metadata_json) if r.metadata_json else {}
                })
            return out
        finally:
            session.close()

def get_db(db_path: str = "data.sqlite") -> Generator[Optional[RateCardStore], None, None]:
    """
    FastAPI dependency that yields a RateCardStore instance.
    """
    store = None
    try:
        store = RateCardStore(db_path=db_path)
        yield store
    finally:
        store = None