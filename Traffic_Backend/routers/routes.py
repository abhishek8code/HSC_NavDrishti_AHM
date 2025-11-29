from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from shapely.geometry import LineString, Point
import Traffic_Backend.models as models
from Traffic_Backend.db_config import SessionLocal
from Traffic_Backend.auth import require_role
from sqlalchemy.orm import Session
import networkx as nx

router = APIRouter(prefix="/routes", tags=["routes"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RouteAnalyzeRequest(BaseModel):
    coordinates: List[List[float]]  # [[lon, lat], ...]


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


@router.post("/analyze", response_model=RouteMetrics)
def analyze_route(payload: RouteAnalyzeRequest, db: Session = Depends(get_db)):
    coords = payload.coordinates
    if len(coords) < 2:
        raise HTTPException(status_code=400, detail="At least two coordinates required")

    ls = LineString([(c[0], c[1]) for c in coords])
    length_deg = ls.length
    # Approximate conversion: 1 degree ~ 111 km (at equator) -> rough estimate
    approx_km = round(length_deg * 111, 4)
    return RouteMetrics(length_degrees=length_deg, num_segments=len(coords)-1, approximate_length_km=approx_km)


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

