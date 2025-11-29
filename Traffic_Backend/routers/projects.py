from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

from Traffic_Backend.db_config import SessionLocal
import Traffic_Backend.models as models
from Traffic_Backend.auth import require_role, get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ProjectStatus(str, Enum):
    planned = "planned"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=128)
    status: ProjectStatus = ProjectStatus.planned
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    resource_allocation: Optional[str] = None
    emission_reduction_estimate: Optional[float] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=128)
    status: Optional[ProjectStatus] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    resource_allocation: Optional[str] = None
    emission_reduction_estimate: Optional[float] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    status: ProjectStatus

    # Pydantic v2 configuration
    model_config = ConfigDict(from_attributes=True)


@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("admin"))])
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = models.Project(
        name=payload.name,
        status=payload.status.value if isinstance(payload.status, ProjectStatus) else payload.status,
        start_time=payload.start_time,
        end_time=payload.end_time,
        start_lat=payload.start_lat,
        start_lon=payload.start_lon,
        end_lat=payload.end_lat,
        end_lon=payload.end_lon,
        resource_allocation=payload.resource_allocation,
        emission_reduction_estimate=payload.emission_reduction_estimate
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(models.Project).all()
    return projects


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectOut, dependencies=[Depends(require_role("admin"))])
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_role("admin"))])
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return None
