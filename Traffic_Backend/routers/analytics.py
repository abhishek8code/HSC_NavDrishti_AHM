"""
Analytics Router
Provides traffic analytics, historical trends, and statistical insights
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, Integer
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import random

from Traffic_Backend.db_config import get_db
from Traffic_Backend.models import TrafficDynamics, RoadNetwork

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Mock data generators for when database is empty
def _generate_mock_traffic_trends(hours: int) -> List:
    """Generate mock traffic trend data"""
    trends = []
    now = datetime.now()
    for i in range(min(hours, 24)):  # Generate hourly data
        timestamp = now - timedelta(hours=i)
        # Simulate rush hour patterns
        hour = timestamp.hour
        base_speed = 40
        if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
            avg_speed = base_speed - random.randint(10, 20)
            vehicle_count = random.randint(80, 150)
            congestion = "high"
        elif 22 <= hour or hour <= 5:  # Night
            avg_speed = base_speed + random.randint(10, 20)
            vehicle_count = random.randint(10, 30)
            congestion = "low"
        else:  # Normal hours
            avg_speed = base_speed + random.randint(-5, 10)
            vehicle_count = random.randint(40, 80)
            congestion = "medium"
        
        trends.append({
            "timestamp": timestamp,
            "avg_speed": round(avg_speed + random.uniform(-3, 3), 2),
            "vehicle_count": vehicle_count,
            "congestion_state": congestion
        })
    return list(reversed(trends))


def _generate_mock_speed_profiles() -> List:
    """Generate mock 24-hour speed profiles"""
    profiles = []
    for hour in range(24):
        if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
            avg_speed = random.uniform(25, 35)
            vehicle_count = random.randint(100, 150)
        elif 22 <= hour or hour <= 5:  # Night
            avg_speed = random.uniform(55, 65)
            vehicle_count = random.randint(10, 25)
        else:  # Normal hours
            avg_speed = random.uniform(40, 50)
            vehicle_count = random.randint(50, 80)
        
        profiles.append({
            "hour": hour,
            "avg_speed": round(avg_speed, 2),
            "vehicle_count": vehicle_count,
            "sample_size": random.randint(20, 50)
        })
    return profiles


# Pydantic models
class TrafficTrend(BaseModel):
    timestamp: datetime
    avg_speed: float
    vehicle_count: int
    congestion_state: str

class SpeedProfile(BaseModel):
    hour: int
    avg_speed: float
    vehicle_count: int
    sample_size: int

class CongestionHeatmap(BaseModel):
    road_segment_id: int
    road_name: Optional[str]
    lat: float
    lon: float
    congestion_score: float  # 0-100
    avg_vehicle_count: int

class AnalyticsSummary(BaseModel):
    total_road_segments: int
    total_traffic_records: int
    avg_speed_kmh: float
    most_congested_segment: Optional[str]
    peak_hour: Optional[int]


@router.get("/traffic-trends")
def get_traffic_trends(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back (1-168)"),
    road_segment_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get historical traffic trends for the last N hours"""
    cutoff = datetime.now() - timedelta(hours=hours)
    
    query = db.query(
        TrafficDynamics.timestamp,
        func.avg(TrafficDynamics.average_speed).label('avg_speed'),
        func.sum(TrafficDynamics.vehicle_count).label('vehicle_count'),
        TrafficDynamics.congestion_state
    ).filter(TrafficDynamics.timestamp >= cutoff)
    
    if road_segment_id:
        query = query.filter(TrafficDynamics.road_segment_id == road_segment_id)
    
    query = query.group_by(
        func.strftime('%Y-%m-%d %H:00:00', TrafficDynamics.timestamp),
        TrafficDynamics.congestion_state
    ).order_by(TrafficDynamics.timestamp)
    
    results = query.all()
    
    # If no data, return mock data
    if not results or len(results) == 0:
        return _generate_mock_traffic_trends(hours)
    
    return [
        {
            "timestamp": row.timestamp,
            "avg_speed": round(row.avg_speed, 2),
            "vehicle_count": row.vehicle_count or 0,
            "congestion_state": row.congestion_state
        }
        for row in results
    ]


@router.get("/speed-profiles")
def get_speed_profiles(
    days: int = Query(7, ge=1, le=30, description="Days to analyze (1-30)"),
    road_segment_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get average speed profiles by hour of day"""
    cutoff = datetime.now() - timedelta(days=days)
    
    query = db.query(
        func.cast(func.strftime('%H', TrafficDynamics.timestamp), Integer).label('hour'),
        func.avg(TrafficDynamics.average_speed).label('avg_speed'),
        func.avg(TrafficDynamics.vehicle_count).label('vehicle_count'),
        func.count(TrafficDynamics.id).label('sample_size')
    ).filter(TrafficDynamics.timestamp >= cutoff)
    
    if road_segment_id:
        query = query.filter(TrafficDynamics.road_segment_id == road_segment_id)
    
    query = query.group_by('hour').order_by('hour')
    
    results = query.all()
    
    # If no data, return mock data
    if not results or len(results) == 0:
        return _generate_mock_speed_profiles()
    
    return [
        {
            "hour": row.hour,
            "avg_speed": round(row.avg_speed, 2) if row.avg_speed else 0,
            "vehicle_count": int(row.vehicle_count) if row.vehicle_count else 0,
            "sample_size": row.sample_size
        }
        for row in results
    ]


@router.get("/congestion-heatmap", response_model=List[CongestionHeatmap])
def get_congestion_heatmap(
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze (1-168)"),
    min_congestion: float = Query(0, ge=0, le=100, description="Minimum congestion score"),
    db: Session = Depends(get_db)
):
    """Get congestion heatmap data for map visualization"""
    cutoff = datetime.now() - timedelta(hours=hours)
    
    # Calculate congestion score based on vehicle count and speed
    # Note: RoadNetwork doesn't have centroid_lat/lon, using dummy values for now
    query = db.query(
        TrafficDynamics.road_segment_id,
        RoadNetwork.name,
        func.avg(TrafficDynamics.vehicle_count).label('avg_vehicle_count'),
        func.avg(TrafficDynamics.average_speed).label('avg_speed')
    ).join(
        RoadNetwork, TrafficDynamics.road_segment_id == RoadNetwork.id
    ).filter(
        TrafficDynamics.timestamp >= cutoff
    ).group_by(
        TrafficDynamics.road_segment_id
    ).all()
    
    heatmap_data = []
    for row in query:
        # Congestion score calculation:
        # Higher vehicle count = more congestion
        # Lower speed = more congestion
        # Normalized to 0-100 scale
        vehicle_factor = min((row.avg_vehicle_count or 0) / 50, 1.0)  # Normalize to 0-1
        speed_factor = 1 - min((row.avg_speed or 0) / 80, 1.0)  # Invert and normalize
        congestion_score = ((vehicle_factor * 0.6) + (speed_factor * 0.4)) * 100
        
        if congestion_score >= min_congestion:
            heatmap_data.append(
                CongestionHeatmap(
                    road_segment_id=row.road_segment_id,
                    road_name=row.name,
                    lat=23.0225,  # Default Ahmedabad center (will use real data later)
                    lon=72.5714,
                    congestion_score=round(congestion_score, 2),
                    avg_vehicle_count=int(row.avg_vehicle_count or 0)
                )
            )
    
    # Sort by congestion score descending
    heatmap_data.sort(key=lambda x: x.congestion_score, reverse=True)
    
    return heatmap_data


@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    """Get overall analytics summary"""
    total_segments = db.query(func.count(RoadNetwork.id)).scalar() or 0
    total_records = db.query(func.count(TrafficDynamics.id)).scalar() or 0
    avg_speed = db.query(func.avg(TrafficDynamics.average_speed)).scalar()
    
    # If no data, return mock summary
    if total_records == 0:
        return {
            "total_road_segments": 45,
            "total_traffic_records": 1250,
            "avg_speed_kmh": 42.5,
            "most_congested_segment": "S.G. Highway",
            "peak_hour": 18
        }
    
    # Most congested segment (highest vehicle count)
    most_congested = db.query(
        RoadNetwork.name,
        func.avg(TrafficDynamics.vehicle_count).label('avg_count')
    ).join(
        TrafficDynamics, RoadNetwork.id == TrafficDynamics.road_segment_id
    ).group_by(
        RoadNetwork.id
    ).order_by(
        func.avg(TrafficDynamics.vehicle_count).desc()
    ).first()
    
    # Peak hour (most traffic)
    peak_hour_result = db.query(
        func.cast(func.strftime('%H', TrafficDynamics.timestamp), int).label('hour'),
        func.sum(TrafficDynamics.vehicle_count).label('total_count')
    ).group_by('hour').order_by(func.sum(TrafficDynamics.vehicle_count).desc()).first()
    
    return {
        "total_road_segments": total_segments,
        "total_traffic_records": total_records,
        "avg_speed_kmh": round(avg_speed, 2) if avg_speed else 0,
        "most_congested_segment": most_congested.name if most_congested else None,
        "peak_hour": peak_hour_result.hour if peak_hour_result else None
    }


@router.get("/export/traffic-data")
def export_traffic_data(
    hours: int = Query(24, ge=1, le=168),
    format: str = Query("csv", regex="^(csv|json)$"),
    db: Session = Depends(get_db)
):
    """Export traffic data in CSV or JSON format"""
    cutoff = datetime.now() - timedelta(hours=hours)
    
    query = db.query(
        TrafficDynamics.timestamp,
        RoadNetwork.name,
        TrafficDynamics.vehicle_count,
        TrafficDynamics.average_speed,
        TrafficDynamics.congestion_state,
        TrafficDynamics.flow_entropy
    ).join(
        RoadNetwork, TrafficDynamics.road_segment_id == RoadNetwork.id
    ).filter(
        TrafficDynamics.timestamp >= cutoff
    ).order_by(TrafficDynamics.timestamp).all()
    
    if format == "csv":
        # Generate CSV
        csv_lines = ["timestamp,road_name,vehicle_count,avg_speed_kmh,congestion_state,flow_entropy"]
        for row in query:
            csv_lines.append(
                f"{row.timestamp},{row.name},{row.vehicle_count},{row.average_speed},"
                f"{row.congestion_state},{row.flow_entropy}"
            )
        
        from fastapi.responses import Response
        return Response(
            content="\n".join(csv_lines),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=traffic_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
    else:
        # JSON format
        data = [
            {
                "timestamp": row.timestamp.isoformat(),
                "road_name": row.name,
                "vehicle_count": row.vehicle_count,
                "avg_speed_kmh": row.average_speed,
                "congestion_state": row.congestion_state,
                "flow_entropy": row.flow_entropy
            }
            for row in query
        ]
        return {"data": data, "total_records": len(data)}
