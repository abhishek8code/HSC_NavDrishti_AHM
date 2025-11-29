from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from shapely.geometry import LineString, Point
import Traffic_Backend.models as models
from Traffic_Backend.db_config import SessionLocal
from Traffic_Backend.auth import require_role
from sqlalchemy.orm import Session
import networkx as nx
import random

router = APIRouter(prefix="/routes", tags=["routes"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RouteAnalyzeRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    waypoints: Optional[List[Dict[str, float]]] = []


class RoadProperties(BaseModel):
    road_type: str
    road_width_m: float
    lanes: int
    surface_type: str


class TrafficCounts(BaseModel):
    total_vehicles: int
    two_wheeler: int
    four_wheeler: int
    heavy_vehicle: int
    avg_speed_kmh: float


class RouteAnalysisResponse(BaseModel):
    distance_km: float
    estimated_time_min: float
    num_points: int
    road_properties: RoadProperties
    traffic_counts: TrafficCounts
    coordinates: List[List[float]]  # Full route coordinates for display


class RouteMetrics(BaseModel):
    length_degrees: float
    num_segments: int
    approximate_length_km: Optional[float] = None


class AlternativeRoute(BaseModel):
    route_id: int
    length_km: float
    num_segments: int
    suitability_score: float
    rank: int


class RecommendationResponse(BaseModel):
    route_id: int
    recommended_alternative_id: Optional[int]
    all_alternatives: List[AlternativeRoute]
    recommendation_justification: str


def _find_nearest_node(point: tuple, graph: nx.DiGraph) -> Optional[tuple]:
    """Find nearest graph node to a (lon, lat) coordinate."""
    if not graph or len(graph.nodes()) == 0:
        return None
    min_dist = float('inf')
    nearest = None
    for node in graph.nodes():
        # node is (lon_rounded, lat_rounded)
        dist = ((point[0] - node[0]) ** 2 + (point[1] - node[1]) ** 2) ** 0.5
        if dist < min_dist:
            min_dist = dist
            nearest = node
    return nearest


def _find_alternatives(start_node: tuple, end_node: tuple, graph: nx.DiGraph, k: int = 3) -> List[List[tuple]]:
    """Find k shortest paths between start and end nodes."""
    if not graph or start_node not in graph.nodes() or end_node not in graph.nodes():
        return []
    try:
        # Get k shortest simple paths
        paths = list(nx.all_simple_paths(graph, start_node, end_node, cutoff=20))
        # Sort by path length and return top k
        paths.sort(key=lambda p: sum(graph[p[i]][p[i+1]].get('length', 0) for i in range(len(p)-1)))
        return paths[:k]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def _score_alternative(path: List[tuple], graph: nx.DiGraph, db: Session) -> float:
    """Score an alternative route based on length and traffic."""
    if len(path) < 2:
        return 0.0
    # Calculate path length
    path_length = sum(graph[path[i]][path[i+1]].get('length', 0) for i in range(len(path)-1))
    # For now, score is inverse of length (shorter is better)
    # Future: incorporate traffic data from DB
    score = 1.0 / (1.0 + path_length)
    return score


@router.post("/analyze", response_model=RouteAnalysisResponse)
def analyze_route(payload: RouteAnalyzeRequest, db: Session = Depends(get_db)):
    """
    Analyze a route defined by start/end coordinates and optional waypoints.
    Returns detailed road properties and traffic analysis.
    """
    # Build coordinate list
    coords = [[payload.start_lon, payload.start_lat]]
    if payload.waypoints:
        coords.extend([[wp['lon'], wp['lat']] for wp in payload.waypoints])
    coords.append([payload.end_lon, payload.end_lat])
    
    if len(coords) < 2:
        raise HTTPException(status_code=400, detail="At least two coordinates required")

    # Calculate distance using Shapely
    ls = LineString([(c[0], c[1]) for c in coords])
    length_deg = ls.length
    # Approximate conversion: 1 degree ~ 111 km (at equator)
    distance_km = round(length_deg * 111, 2)
    
    # Estimate road properties based on distance and location
    road_props = _estimate_road_properties(distance_km, coords)
    
    # Estimate traffic counts (would query real traffic database in production)
    traffic_counts = _estimate_traffic_counts(distance_km, road_props)
    
    # Calculate estimated travel time
    avg_speed = traffic_counts.avg_speed_kmh
    estimated_time_min = round((distance_km / avg_speed) * 60, 1) if avg_speed > 0 else 0
    
    return RouteAnalysisResponse(
        distance_km=distance_km,
        estimated_time_min=estimated_time_min,
        num_points=len(coords),
        road_properties=road_props,
        traffic_counts=traffic_counts,
        coordinates=coords
    )


def _estimate_road_properties(distance_km: float, coords: List[List[float]]) -> RoadProperties:
    """Estimate road properties based on route characteristics."""
    # Mock estimation - in production, query GIS database
    
    if distance_km > 10:
        return RoadProperties(
            road_type="Highway",
            road_width_m=12.0,
            lanes=4,
            surface_type="Asphalt"
        )
    elif distance_km > 5:
        return RoadProperties(
            road_type="Main Road",
            road_width_m=10.0,
            lanes=4,
            surface_type="Asphalt"
        )
    elif distance_km > 1:
        return RoadProperties(
            road_type="Urban Road",
            road_width_m=7.5,
            lanes=2,
            surface_type="Asphalt"
        )
    else:
        return RoadProperties(
            road_type="Local Street",
            road_width_m=5.0,
            lanes=1,
            surface_type="Concrete"
        )


def _estimate_traffic_counts(distance_km: float, road_props: RoadProperties) -> TrafficCounts:
    """Estimate traffic vehicle counts based on road type and distance."""
    # Mock estimation - in production, query traffic sensors/historical data
    
    # Base vehicles per km per hour based on road type
    base_density = {
        "Highway": 800,
        "Main Road": 600,
        "Urban Road": 400,
        "Local Street": 200
    }
    
    base = base_density.get(road_props.road_type, 400)
    total = int(base * distance_km)
    
    # Distribution percentages (typical for Indian cities)
    two_wheeler = int(total * 0.45)  # 45% two-wheelers
    four_wheeler = int(total * 0.40)  # 40% cars
    heavy = int(total * 0.15)  # 15% buses/trucks
    
    # Average speed based on road type
    avg_speed_map = {
        "Highway": 80.0,
        "Main Road": 50.0,
        "Urban Road": 35.0,
        "Local Street": 20.0
    }
    
    return TrafficCounts(
        total_vehicles=total,
        two_wheeler=two_wheeler,
        four_wheeler=four_wheeler,
        heavy_vehicle=heavy,
        avg_speed_kmh=avg_speed_map.get(road_props.road_type, 35.0)
    )


@router.get("/{route_id}/metrics")
def route_metrics(route_id: int, db: Session = Depends(get_db)):
    segment = db.query(models.RoadNetwork).filter(models.RoadNetwork.id == route_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Route segment not found")

    dynamics = db.query(models.TrafficDynamics).filter(models.TrafficDynamics.road_segment_id == route_id).all()
    vehicle_count = sum((d.vehicle_count or 0) for d in dynamics)
    avg_speed = None
    if dynamics:
        speeds = [d.average_speed for d in dynamics if d.average_speed is not None]
        if speeds:
            avg_speed = sum(speeds) / len(speeds)

    return {
        "route_id": route_id,
        "segment_name": segment.name,
        "base_capacity": segment.base_capacity,
        "vehicle_count_sum": vehicle_count,
        "average_speed": avg_speed
    }


@router.get("/{route_id}/alternatives")
def route_alternatives(route_id: int, start_lon: float, start_lat: float, end_lon: float, end_lat: float, db: Session = Depends(get_db)):
    """Get alternative routes between start and end coordinates."""
    # Import here to avoid circular imports
    from Traffic_Backend.main import road_network_graph
    
    if road_network_graph is None or len(road_network_graph.nodes()) == 0:
        raise HTTPException(status_code=400, detail="Road network not loaded")

    # Find nearest nodes
    start_node = _find_nearest_node((start_lon, start_lat), road_network_graph)
    end_node = _find_nearest_node((end_lon, end_lat), road_network_graph)
    
    if not start_node or not end_node:
        raise HTTPException(status_code=400, detail="Could not locate start or end coordinate on road network")

    # Find alternative paths
    paths = _find_alternatives(start_node, end_node, road_network_graph, k=3)
    
    if not paths:
        return {"route_id": route_id, "alternatives": []}

    # Score and rank alternatives
    alternatives = []
    for idx, path in enumerate(paths):
        path_length = sum(road_network_graph[path[i]][path[i+1]].get('length', 0) for i in range(len(path)-1))
        approx_km = round(path_length * 111, 4)
        score = _score_alternative(path, road_network_graph, db)
        alternatives.append(AlternativeRoute(route_id=idx, length_km=approx_km, num_segments=len(path)-1, suitability_score=score, rank=idx+1))

    return {"route_id": route_id, "alternatives": alternatives}


@router.post("/{route_id}/recommend", response_model=RecommendationResponse)
def route_recommend(route_id: int, start_lon: float, start_lat: float, end_lon: float, end_lat: float, db: Session = Depends(get_db)):
    """Get recommended alternative route based on suitability scoring."""
    from Traffic_Backend.main import road_network_graph
    
    if road_network_graph is None or len(road_network_graph.nodes()) == 0:
        raise HTTPException(status_code=400, detail="Road network not loaded")

    start_node = _find_nearest_node((start_lon, start_lat), road_network_graph)
    end_node = _find_nearest_node((end_lon, end_lat), road_network_graph)
    
    if not start_node or not end_node:
        raise HTTPException(status_code=400, detail="Could not locate start or end coordinate on road network")

    paths = _find_alternatives(start_node, end_node, road_network_graph, k=3)
    
    if not paths:
        return RecommendationResponse(route_id=route_id, recommended_alternative_id=None, all_alternatives=[], recommendation_justification="No alternative routes found")

    alternatives = []
    for idx, path in enumerate(paths):
        path_length = sum(road_network_graph[path[i]][path[i+1]].get('length', 0) for i in range(len(path)-1))
        approx_km = round(path_length * 111, 4)
        score = _score_alternative(path, road_network_graph, db)
        alternatives.append(AlternativeRoute(route_id=idx, length_km=approx_km, num_segments=len(path)-1, suitability_score=score, rank=idx+1))

    # Recommend the highest-scoring alternative
    best_alt = max(alternatives, key=lambda a: a.suitability_score)
    justification = f"Route {best_alt.route_id} recommended: length {best_alt.length_km} km, score {best_alt.suitability_score:.4f}"
    
    return RecommendationResponse(route_id=route_id, recommended_alternative_id=best_alt.route_id, all_alternatives=alternatives, recommendation_justification=justification)


@router.post("/recommend")
def recommend_routes(payload: RouteAnalyzeRequest, db: Session = Depends(get_db)):
    """
    Lightweight recommendation endpoint that accepts the frontend payload shape
    and returns a deterministic set of mock alternative routes for UI testing.
    This is intended as a development stub until a production recommender is available.
    """
    # Build coordinate list
    coords = [[payload.start_lon, payload.start_lat]]
    if payload.waypoints:
        coords.extend([[wp['lon'], wp['lat']] for wp in payload.waypoints])
    coords.append([payload.end_lon, payload.end_lat])

    # Generate simple mock alternatives by perturbing coordinates slightly
    alts = []
    for i in range(3):
        factor = (i - 1) * 0.001
        perturbed = [[c[0] + factor * (random.random() - 0.5), c[1] + factor * (random.random() - 0.5)] for c in coords]
        ls = LineString([(c[0], c[1]) for c in perturbed])
        dist_km = round(ls.length * 111, 4)
        alts.append({
            "id": f"mock-{i+1}",
            "name": f"Alt {i+1}",
            "coordinates": perturbed,
            "distance_km": dist_km,
            "travel_time_min": max(1, int(dist_km * 2)),
            "traffic_score": round(random.random(), 3),
            "emission_g": int(random.random() * 1000),
            "rank": i+1
        })

    return {"routes": alts}

