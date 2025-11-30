"""
GPS Vehicle Tracking Router
Provides real-time vehicle location tracking with WebSocket support
"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import json

from Traffic_Backend.db_config import get_db
from Traffic_Backend.models import Vehicle

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass  # Connection might be closed

manager = ConnectionManager()


# Pydantic models
class VehicleRegister(BaseModel):
    vehicle_id: str
    vehicle_type: str  # 'bus', 'truck', 'emergency', 'patrol'
    driver_name: Optional[str] = None

class VehicleLocation(BaseModel):
    lat: float
    lon: float
    speed: Optional[float] = None  # km/h
    heading: Optional[float] = None  # degrees (0-360)

class VehicleResponse(BaseModel):
    id: int
    vehicle_id: str
    vehicle_type: str
    driver_name: Optional[str]
    current_lat: Optional[float]
    current_lon: Optional[float]
    status: str
    speed: Optional[float]
    heading: Optional[float]
    last_update: Optional[datetime]
    registration_date: datetime

    class Config:
        from_attributes = True


# REST API Endpoints
@router.post("/register", response_model=VehicleResponse)
def register_vehicle(vehicle: VehicleRegister, db: Session = Depends(get_db)):
    """Register a new vehicle in the system"""
    # Check if vehicle already exists
    existing = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle already registered")
    
    db_vehicle = Vehicle(
        vehicle_id=vehicle.vehicle_id,
        vehicle_type=vehicle.vehicle_type,
        driver_name=vehicle.driver_name,
        status='offline',
        registration_date=datetime.now()
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


@router.get("/", response_model=List[VehicleResponse])
def get_all_vehicles(
    status: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all vehicles with optional filters"""
    query = db.query(Vehicle)
    
    if status:
        query = query.filter(Vehicle.status == status)
    if vehicle_type:
        query = query.filter(Vehicle.vehicle_type == vehicle_type)
    
    return query.all()


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(vehicle_id: str, db: Session = Depends(get_db)):
    """Get vehicle details by vehicle_id"""
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.post("/{vehicle_id}/location")
async def update_vehicle_location(
    vehicle_id: str,
    location: VehicleLocation,
    db: Session = Depends(get_db)
):
    """Update vehicle location and broadcast to WebSocket clients"""
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Update vehicle location
    vehicle.current_lat = location.lat
    vehicle.current_lon = location.lon
    vehicle.speed = location.speed
    vehicle.heading = location.heading
    vehicle.last_update = datetime.now()
    vehicle.status = 'active'
    
    db.commit()
    db.refresh(vehicle)
    
    # Broadcast to WebSocket clients
    await manager.broadcast({
        "type": "location_update",
        "vehicle_id": vehicle_id,
        "data": {
            "lat": location.lat,
            "lon": location.lon,
            "speed": location.speed,
            "heading": location.heading,
            "vehicle_type": vehicle.vehicle_type,
            "status": vehicle.status,
            "timestamp": datetime.now().isoformat()
        }
    })
    
    return {
        "message": "Location updated",
        "vehicle_id": vehicle_id,
        "timestamp": vehicle.last_update
    }


@router.delete("/{vehicle_id}")
def deregister_vehicle(vehicle_id: str, db: Session = Depends(get_db)):
    """Remove vehicle from tracking system"""
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    db.delete(vehicle)
    db.commit()
    return {"message": "Vehicle deregistered", "vehicle_id": vehicle_id}


@router.post("/{vehicle_id}/status")
def update_vehicle_status(
    vehicle_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """Update vehicle status (active, idle, offline)"""
    if status not in ['active', 'idle', 'offline']:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    vehicle.status = status
    db.commit()
    
    return {"message": "Status updated", "vehicle_id": vehicle_id, "status": status}


# WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time vehicle tracking"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
