from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import Traffic_Backend.models as models
from Traffic_Backend.db_config import SessionLocal
from Traffic_Backend.auth import require_role

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class NotificationPayload(BaseModel):
    project_id: Optional[int] = None
    recipient_type: str  # 'admin' or 'public'
    message: str
    template: Optional[str] = None


class NotificationOut(BaseModel):
    id: int
    project_id: Optional[int]
    recipient_type: str
    message: str
    timestamp: datetime
    delivery_status: str


TEMPLATES = {
    "default_admin": "Project {project_id} requires approval.",
    "public_update": "Construction update for project {project_id}: {message}"
}


@router.post("/send", dependencies=[Depends(require_role("admin"))])
def send_notification(payload: NotificationPayload, db: Session = Depends(get_db)):
    """Send and persist a notification."""
    notification = models.Notification(
        project_id=payload.project_id,
        recipient_type=payload.recipient_type,
        message=payload.message,
        template=payload.template,
        timestamp=datetime.utcnow(),
        delivery_status="sent"
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return {"sent": True, "notification_id": notification.id, "timestamp": notification.timestamp}


@router.get("/log")
def get_log(limit: int = 100, db: Session = Depends(get_db)):
    """Get notification log from DB."""
    entries = db.query(models.Notification).order_by(models.Notification.timestamp.desc()).limit(limit).all()
    return {"total": len(entries), "entries": [
        {"id": e.id, "project_id": e.project_id, "recipient_type": e.recipient_type, "message": e.message, "timestamp": e.timestamp, "status": e.delivery_status} for e in entries
    ]}


@router.get("/templates")
def get_templates():
    """Get available notification templates."""
    return {"templates": TEMPLATES}

