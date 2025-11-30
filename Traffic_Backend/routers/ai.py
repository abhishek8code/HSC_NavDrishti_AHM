"""
AI Router
AI-powered prediction, anomaly detection, and route recommendation endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import pandas as pd

from Traffic_Backend.db_config import get_db
from Traffic_Backend.models import TrafficDynamics, RoadNetwork
from Traffic_Backend.ai_predictor import predictor

router = APIRouter(prefix="/ai", tags=["ai"])


# Pydantic models
class PredictionRequest(BaseModel):
    road_segment_id: Optional[int] = None
    prediction_time: Optional[datetime] = None
    horizon_hours: int = 4

class SpeedPrediction(BaseModel):
    time: datetime
    predicted_speed: float
    confidence: float
    congestion_state: str
    lower_bound: float
    upper_bound: float

class RouteRecommendationRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    vehicle_type: str = 'car'
    time_preference: str = 'fastest'  # 'fastest', 'shortest', 'safest'
    avoid_congestion: bool = True

class Anomaly(BaseModel):
    road_segment_id: int
    road_name: Optional[str]
    anomaly_type: str
    severity: str
    anomaly_score: float
    description: str
    detected_at: datetime
    location: Dict[str, float]


@router.post("/predict-speed", response_model=List[SpeedPrediction])
async def predict_speed(request: PredictionRequest, db: Session = Depends(get_db)):
    """
    Predict traffic speed for next N hours
    Uses Random Forest model trained on historical data
    """
    try:
        # Get historical data for the road segment
        historical_data = None
        if request.road_segment_id:
            cutoff = datetime.now() - timedelta(days=30)
            query = db.query(TrafficDynamics).filter(
                TrafficDynamics.road_segment_id == request.road_segment_id,
                TrafficDynamics.timestamp >= cutoff
            ).all()
            
            if query:
                historical_data = pd.DataFrame([
                    {
                        'timestamp': td.timestamp,
                        'average_speed': td.average_speed,
                        'vehicle_count': td.vehicle_count,
                        'road_segment_id': td.road_segment_id
                    }
                    for td in query
                ])
        
        # Generate predictions
        predictions = []
        start_time = request.prediction_time or datetime.now()
        
        for i in range(request.horizon_hours):
            prediction_time = start_time + timedelta(hours=i)
            
            result = predictor.predict_speed(
                prediction_time,
                request.road_segment_id or 1,
                historical_data
            )
            
            congestion = predictor.predict_congestion(result['predicted_speed'])
            
            predictions.append(SpeedPrediction(
                time=prediction_time,
                predicted_speed=result['predicted_speed'],
                confidence=result['confidence'],
                congestion_state=congestion,
                lower_bound=result['lower_bound'],
                upper_bound=result['upper_bound']
            ))
        
        return predictions
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict-congestion")
async def predict_congestion(request: PredictionRequest, db: Session = Depends(get_db)):
    """
    Predict congestion levels for next N hours
    """
    try:
        speed_predictions = await predict_speed(request, db)
        
        return {
            "predictions": [
                {
                    "time": pred.time.isoformat(),
                    "congestion_state": pred.congestion_state,
                    "confidence": pred.confidence,
                    "predicted_speed": pred.predicted_speed
                }
                for pred in speed_predictions
            ],
            "road_segment_id": request.road_segment_id,
            "model_used": "random_forest",
            "horizon_hours": request.horizon_hours
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/anomalies", response_model=List[Anomaly])
async def detect_anomalies(
    hours: int = Query(24, ge=1, le=168),
    severity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Detect traffic anomalies using Isolation Forest
    """
    try:
        # Get recent traffic data
        cutoff = datetime.now() - timedelta(hours=hours)
        query = db.query(
            TrafficDynamics,
            RoadNetwork.name
        ).join(
            RoadNetwork,
            TrafficDynamics.road_segment_id == RoadNetwork.id
        ).filter(
            TrafficDynamics.timestamp >= cutoff
        ).all()
        
        if not query:
            return []
        
        # Prepare data
        current_data = pd.DataFrame([
            {
                'timestamp': td.timestamp,
                'average_speed': td.average_speed or 0,
                'vehicle_count': td.vehicle_count or 0,
                'road_segment_id': td.road_segment_id,
                'road_name': name
            }
            for td, name in query
        ])
        
        # Get historical data for training anomaly detector
        historical_cutoff = datetime.now() - timedelta(days=30)
        historical_query = db.query(TrafficDynamics).filter(
            TrafficDynamics.timestamp >= historical_cutoff,
            TrafficDynamics.timestamp < cutoff
        ).all()
        
        historical_data = None
        if historical_query:
            historical_data = pd.DataFrame([
                {
                    'average_speed': td.average_speed or 0,
                    'vehicle_count': td.vehicle_count or 0
                }
                for td in historical_query
            ])
        
        # Detect anomalies
        detected = predictor.detect_anomalies(current_data, historical_data)
        
        # Convert to response format
        anomalies = []
        for anom in detected:
            if severity and anom['severity'] != severity:
                continue
            
            # Find road info
            road_info = current_data[
                current_data['road_segment_id'] == anom['road_segment_id']
            ].iloc[0]
            
            description = f"{anom['anomaly_type'].replace('_', ' ').title()} detected"
            if anom['anomaly_type'] == 'severe_slowdown':
                description += f" (speed: {anom['speed']} km/h)"
            elif anom['anomaly_type'] == 'high_volume':
                description += f" (vehicles: {anom['vehicle_count']})"
            
            anomalies.append(Anomaly(
                road_segment_id=anom['road_segment_id'],
                road_name=road_info['road_name'],
                anomaly_type=anom['anomaly_type'],
                severity=anom['severity'],
                anomaly_score=anom['anomaly_score'],
                description=description,
                detected_at=anom['timestamp'],
                location={'lat': 23.0225, 'lon': 72.5714}  # Default Ahmedabad
            ))
        
        return anomalies
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")


@router.post("/recommend-route")
async def recommend_route(request: RouteRecommendationRequest):
    """
    AI-powered route recommendation
    Considers historical patterns, predicted traffic, and user preferences
    """
    try:
        recommendation = predictor.recommend_route(
            origin=(request.origin_lat, request.origin_lon),
            destination=(request.dest_lat, request.dest_lon),
            vehicle_type=request.vehicle_type,
            time_preference=request.time_preference
        )
        
        return {
            "recommended_routes": [
                {
                    "rank": 1,
                    "route_geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [request.origin_lon, request.origin_lat],
                            [request.dest_lon, request.dest_lat]
                        ]
                    },
                    "estimated_time_min": recommendation['estimated_time_min'],
                    "distance_km": recommendation['estimated_distance_km'],
                    "confidence": recommendation['confidence'],
                    "factors": recommendation['factors'],
                    "route_type": recommendation['route_type']
                }
            ],
            "vehicle_type": request.vehicle_type,
            "time_preference": request.time_preference
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route recommendation failed: {str(e)}")


@router.get("/model-stats")
async def get_model_stats():
    """
    Get AI model statistics and performance metrics
    """
    try:
        stats = predictor.get_model_stats()
        
        return {
            "models": {
                "speed_prediction": {
                    "status": "active" if stats['speed_model_loaded'] else "not_trained",
                    "type": stats['model_type'],
                    "last_trained": stats['last_trained'],
                    "features_count": stats['features_count']
                },
                "anomaly_detection": {
                    "status": "active" if stats['anomaly_detector_ready'] else "inactive",
                    "type": "isolation_forest",
                    "contamination": 0.1
                },
                "route_recommendation": {
                    "status": "active",
                    "type": "heuristic_ml_hybrid"
                }
            },
            "server_time": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/train-model")
async def train_model(
    background_tasks: BackgroundTasks,
    days: int = Query(30, ge=7, le=180),
    db: Session = Depends(get_db)
):
    """
    Train/retrain AI models on historical data
    Runs in background to avoid blocking
    """
    def train_task():
        try:
            # Get historical data
            cutoff = datetime.now() - timedelta(days=days)
            query = db.query(TrafficDynamics).filter(
                TrafficDynamics.timestamp >= cutoff
            ).all()
            
            if len(query) < 50:
                print(f"Insufficient data for training: {len(query)} samples")
                return
            
            training_data = pd.DataFrame([
                {
                    'timestamp': td.timestamp,
                    'average_speed': td.average_speed or 40.0,
                    'vehicle_count': td.vehicle_count or 0,
                    'road_segment_id': td.road_segment_id
                }
                for td in query
            ])
            
            # Train speed prediction model
            accuracy = predictor.train_speed_model(training_data)
            print(f"Model trained successfully. Accuracy: {accuracy:.3f}")
        
        except Exception as e:
            print(f"Training failed: {str(e)}")
    
    background_tasks.add_task(train_task)
    
    return {
        "message": "Model training started in background",
        "training_days": days,
        "status": "processing"
    }
