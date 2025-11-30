from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
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


@router.get("/live")
def traffic_live_all(db: Session = Depends(get_db)):
    """
    Returns live traffic data for all segments with congestion levels.
    Generates mock data for Ahmedabad area if no real data exists.
    """
    # Try to get real data from database
    entries = db.query(models.TrafficDynamics).order_by(models.TrafficDynamics.timestamp.desc()).limit(100).all()
    
    if entries:
        # Return real data if available
        segments = []
        for entry in entries:
            segment = db.query(models.RoadNetwork).filter(models.RoadNetwork.id == entry.road_segment_id).first()
            if segment:
                # Calculate congestion level (0.0 to 1.0)
                congestion = 0.5  # default
                if entry.average_speed:
                    # Lower speed = higher congestion
                    congestion = max(0.0, min(1.0, 1.0 - (entry.average_speed / 80.0)))
                
                segments.append({
                    "segment_id": f"seg_{entry.road_segment_id}",
                    "coordinates": [[segment.start_lon, segment.start_lat], [segment.end_lon, segment.end_lat]],
                    "congestion_level": round(congestion, 2),
                    "speed_kmh": entry.average_speed or 30,
                    "vehicle_count": entry.vehicle_count or 0,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else datetime.now().isoformat()
                })
        
        return {"segments": segments, "timestamp": datetime.now().isoformat()}
    
    # Generate mock traffic data for Ahmedabad area
    mock_segments = _generate_mock_traffic_segments()
    return {"segments": mock_segments, "timestamp": datetime.now().isoformat(), "mock": True}


def _generate_mock_traffic_segments():
    """
    Generate mock traffic segments for Ahmedabad area.
    Creates realistic-looking traffic data on major roads.
    """
    # Ahmedabad major roads (approximate coordinates)
    major_roads = [
        # SG Highway
        {"start": [72.5200, 23.0300], "end": [72.5400, 23.0500], "name": "SG Highway North"},
        {"start": [72.5400, 23.0500], "end": [72.5600, 23.0700], "name": "SG Highway Central"},
        {"start": [72.5600, 23.0700], "end": [72.5800, 23.0900], "name": "SG Highway South"},
        
        # Ashram Road
        {"start": [72.5800, 23.0200], "end": [72.5900, 23.0400], "name": "Ashram Road"},
        
        # CG Road
        {"start": [72.5500, 23.0300], "end": [72.5700, 23.0350], "name": "CG Road"},
        
        # Nehru Bridge area
        {"start": [72.5850, 23.0350], "end": [72.5950, 23.0400], "name": "Nehru Bridge"},
        
        # Paldi area
        {"start": [72.5600, 23.0200], "end": [72.5700, 23.0250], "name": "Paldi Road"},
        
        # Maninagar
        {"start": [72.6000, 23.0100], "end": [72.6100, 23.0200], "name": "Maninagar Road"},
    ]
    
    segments = []
    for i, road in enumerate(major_roads):
        # Vary congestion by time simulation
        base_congestion = random.uniform(0.2, 0.8)
        congestion = max(0.0, min(1.0, base_congestion + random.uniform(-0.1, 0.1)))
        
        # Speed inversely related to congestion
        max_speed = 60
        speed = max(10, int(max_speed * (1 - congestion)))
        
        # Vehicle count based on congestion
        vehicle_count = int(50 + congestion * 150)
        
        segments.append({
            "segment_id": f"seg_{i+1:03d}",
            "name": road["name"],
            "coordinates": [road["start"], road["end"]],
            "congestion_level": round(congestion, 2),
            "speed_kmh": speed,
            "vehicle_count": vehicle_count,
            "timestamp": datetime.now().isoformat()
        })
    
    return segments


@router.get("/alerts")
def traffic_alerts(db: Session = Depends(get_db)):
    """
    Returns active traffic alerts (accidents, construction, congestion).
    Generates mock alerts if no real data exists.
    """
    # Check for real alerts in notifications or thresholds
    # For now, generate mock alerts
    mock_alerts = _generate_mock_alerts()
    return {"alerts": mock_alerts, "timestamp": datetime.now().isoformat()}


def _generate_mock_alerts():
    """
    Generate mock traffic alerts for demo purposes.
    """
    alert_types = [
        {"type": "accident", "severity": "high", "icon": "⚠️"},
        {"type": "construction", "severity": "medium", "icon": "🚧"},
        {"type": "congestion", "severity": "medium", "icon": "🚗"},
        {"type": "event", "severity": "low", "icon": "📅"},
    ]
    
    # Ahmedabad locations for alerts
    alert_locations = [
        {"lat": 23.0450, "lon": 72.5570, "area": "SG Highway near Shyamal"},
        {"lat": 23.0225, "lon": 72.5714, "area": "Ashram Road"},
        {"lat": 23.0350, "lon": 72.5850, "area": "Nehru Bridge"},
        {"lat": 23.0300, "lon": 72.5650, "area": "Panjrapole"},
    ]
    
    alerts = []
    num_alerts = random.randint(2, 4)  # Generate 2-4 alerts
    
    for i in range(num_alerts):
        alert_type = random.choice(alert_types)
        location = random.choice(alert_locations)
        
        messages = {
            "accident": f"Multi-vehicle accident reported at {location['area']}",
            "construction": f"Road work in progress at {location['area']}",
            "congestion": f"Heavy traffic congestion at {location['area']}",
            "event": f"Special event causing delays near {location['area']}"
        }
        
        alerts.append({
            "id": i + 1,
            "type": alert_type["type"],
            "severity": alert_type["severity"],
            "icon": alert_type["icon"],
            "location": [location["lon"], location["lat"]],
            "area": location["area"],
            "message": messages[alert_type["type"]],
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(5, 60))).isoformat(),
            "affected_routes": [1, 2] if alert_type["severity"] == "high" else []
        })
    
    return alerts

