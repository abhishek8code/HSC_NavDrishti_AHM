from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    start_lat = Column(Float)
    start_lon = Column(Float)
    end_lat = Column(Float)
    end_lon = Column(Float)
    resource_allocation = Column(Text)
    emission_reduction_estimate = Column(Float)
    road_segment_id = Column(Integer, ForeignKey('road_network.id'))
    road_segment = relationship('RoadNetwork')

class RoadNetwork(Base):
    __tablename__ = 'road_network'
    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    geometry = Column(Text)  # WKT or GeoJSON
    base_capacity = Column(Integer)
    roughness_index = Column(Float)

class TrafficDynamics(Base):
    __tablename__ = 'traffic_dynamics'
    id = Column(Integer, primary_key=True)
    road_segment_id = Column(Integer, ForeignKey('road_network.id'))
    timestamp = Column(DateTime)
    flow_entropy = Column(Float)
    congestion_state = Column(String(32))
    vehicle_count = Column(Integer)
    average_speed = Column(Float)
    road_segment = relationship('RoadNetwork')

class DamageCluster(Base):
    __tablename__ = 'damage_clusters'
    id = Column(Integer, primary_key=True)
    centroid_lat = Column(Float)
    centroid_lon = Column(Float)
    avg_severity = Column(Float)
    count = Column(Integer)
    road_segment_id = Column(Integer, ForeignKey('road_network.id'))
    road_segment = relationship('RoadNetwork')


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Integer, default=1)
    roles = Column(String(255), default='')  # comma-separated roles


class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    recipient_type = Column(String(32), nullable=False)  # 'admin' or 'public'
    message = Column(Text, nullable=False)
    template = Column(String(128), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    delivery_status = Column(String(32), default='sent')


class TrafficThreshold(Base):
    __tablename__ = 'traffic_thresholds'
    id = Column(Integer, primary_key=True)
    road_segment_id = Column(Integer, ForeignKey('road_network.id'), nullable=False)
    vehicle_count_limit = Column(Integer, nullable=True)
    density_limit = Column(Float, nullable=True)
    alert_type = Column(String(32), nullable=True)
    is_active = Column(Integer, default=1)

