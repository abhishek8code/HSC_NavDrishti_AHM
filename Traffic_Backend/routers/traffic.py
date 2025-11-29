from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import Traffic_Backend.models as models
from Traffic_Backend.db_config import SessionLocal
from Traffic_Backend.auth import require_role, get_current_user

router = APIRouter(prefix="/traffic", tags=["traffic"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TrafficThreshold(BaseModel):
    route_id: int
    vehicle_count_limit: Optional[int] = None
    density_limit: Optional[float] = None


@router.get("/live/{route_id}")
def traffic_live(route_id: int, db: Session = Depends(get_db)):
    # Return the latest TrafficDynamics entry for route
    entry = db.query(models.TrafficDynamics).filter(models.TrafficDynamics.road_segment_id == route_id).order_by(models.TrafficDynamics.timestamp.desc()).first()
    if not entry:
        raise HTTPException(status_code=404, detail="No live data for this route")
    return {
        "route_id": route_id,
        "timestamp": entry.timestamp,
        "vehicle_count": entry.vehicle_count,
        "average_speed": entry.average_speed,
        "congestion_state": entry.congestion_state
    }


@router.get("/history/{route_id}")
def traffic_history(route_id: int, limit: int = 100, db: Session = Depends(get_db)):
    entries = db.query(models.TrafficDynamics).filter(models.TrafficDynamics.road_segment_id == route_id).order_by(models.TrafficDynamics.timestamp.desc()).limit(limit).all()
    return {"route_id": route_id, "count": len(entries), "entries": [
        {"timestamp": e.timestamp, "vehicle_count": e.vehicle_count, "avg_speed": e.average_speed, "congestion_state": e.congestion_state} for e in entries
    ]}


@router.post("/threshold/configure", dependencies=[Depends(require_role("admin"))])
def configure_threshold(payload: TrafficThreshold, db: Session = Depends(get_db)):
    # Check if threshold already exists for this road segment
    existing = db.query(models.TrafficThreshold).filter(models.TrafficThreshold.road_segment_id == payload.route_id).first()
    if existing:
        existing.vehicle_count_limit = payload.vehicle_count_limit
        existing.density_limit = payload.density_limit
        db.add(existing)
    else:
        threshold = models.TrafficThreshold(
            road_segment_id=payload.route_id,
            vehicle_count_limit=payload.vehicle_count_limit,
            density_limit=payload.density_limit
        )
        db.add(threshold)
    db.commit()
    return {"road_segment_id": payload.route_id, "configured": True}


@router.get("/threshold/{route_id}")
def get_threshold(route_id: int, db: Session = Depends(get_db)):
    threshold = db.query(models.TrafficThreshold).filter(models.TrafficThreshold.road_segment_id == route_id).first()
    if not threshold:
        return {"road_segment_id": route_id, "threshold": None}
    return {
        "road_segment_id": route_id,
        "threshold": {
            "vehicle_count_limit": threshold.vehicle_count_limit,
            "density_limit": threshold.density_limit
        }
    }

