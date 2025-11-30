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
import os
import httpx
import json
from urllib.parse import quote

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


class OptimizationStop(BaseModel):
    lon: float
    lat: float
    name: Optional[str] = None


class OptimizationRequest(BaseModel):
    coordinates: List[OptimizationStop]
    source: str = "first"  # "first", "last", "any"
    destination: str = "last"  # "first", "last", "any"
    roundtrip: bool = True
    profile: str = "driving-traffic"


class MatrixRequest(BaseModel):
    coordinates: List[Dict[str, float]]
    profile: str = "driving-traffic"


class MapMatchingRequest(BaseModel):
    coordinates: List[Dict[str, float]]
    timestamps: Optional[List[str]] = None


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


class MatrixRequest(BaseModel):
    coordinates: List[Dict[str, float]]
    profile: str = "driving-traffic"


class MapMatchingRequest(BaseModel):
    coordinates: List[Dict[str, float]]
    timestamps: Optional[List[str]] = None


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


@router.get("/geocode/forward")
async def geocode_forward(query: str):
    """
    Forward Geocoding: Convert address/place name to coordinates
    
    Args:
        query: Address or place name (e.g., "SG Highway, Ahmedabad")
    
    Returns:
        List of matching locations with coordinates
    """
    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return {"error": "Mapbox token not configured", "results": []}
    
    try:
        encoded_query = quote(query)
        # Limit search to Ahmedabad area for better results
        proximity = "72.5714,23.0225"  # Ahmedabad center
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
        params = {
            "access_token": mapbox_token,
            "proximity": proximity,
            "limit": 5,
            "types": "place,locality,neighborhood,address,poi"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                # Surface Mapbox error details to aid debugging
                return {
                    "error": f"Geocoding failed: status {response.status_code}",
                    "details": response.text,
                    "results": []
                }
            data = response.json()
            
            results = []
            for feature in data.get("features", []):
                coords = feature["geometry"]["coordinates"]
                results.append({
                    "place_name": feature["place_name"],
                    "lon": coords[0],
                    "lat": coords[1],
                    "type": feature.get("place_type", ["unknown"])[0],
                    "relevance": feature.get("relevance", 0)
                })
            
            return {"query": query, "results": results}
    
    except httpx.HTTPError as e:
        return {"error": f"Geocoding failed: {str(e)}", "results": []}


@router.get("/geocode/reverse")
async def geocode_reverse(lon: float, lat: float):
    """
    Reverse Geocoding: Convert coordinates to address
    
    Args:
        lon: Longitude
        lat: Latitude
    
    Returns:
        Address information for the location
    """
    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return {"error": "Mapbox token not configured", "address": "Unknown"}
    
    try:
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{lon},{lat}.json"
        params = {
            "access_token": mapbox_token,
            "types": "address,place,locality,neighborhood"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return {
                    "error": f"Reverse geocoding failed: status {response.status_code}",
                    "details": response.text,
                    "address": "Unknown"
                }
            data = response.json()
            
            if data.get("features"):
                feature = data["features"][0]
                return {
                    "address": feature["place_name"],
                    "lon": lon,
                    "lat": lat,
                    "type": feature.get("place_type", ["unknown"])[0]
                }
            else:
                return {"address": "Unknown location", "lon": lon, "lat": lat}
    
    except httpx.HTTPError as e:
        return {"error": f"Reverse geocoding failed: {str(e)}", "address": "Unknown"}


@router.get("/isochrone")
async def get_isochrone(
    lon: float,
    lat: float,
    minutes: int = 15,
    profile: str = "driving-traffic"
):
    """
    Isochrone API: Get area reachable within specified time
    
    Args:
        lon: Starting longitude
        lat: Starting latitude
        minutes: Travel time in minutes (default: 15)
        profile: Routing profile (driving-traffic, walking, cycling)
    
    Returns:
        GeoJSON polygon of reachable area
    """
    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return {"error": "Mapbox token not configured"}
    
    try:
        # Convert minutes to seconds
        contours_minutes = min(minutes, 60)  # Max 60 minutes
        url = f"https://api.mapbox.com/isochrone/v1/mapbox/{profile}/{lon},{lat}"
        params = {
            "contours_minutes": contours_minutes,
            "polygons": "true",
            "access_token": mapbox_token
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return {"error": f"Isochrone failed: status {response.status_code}", "details": response.text}
            data = response.json()
            
            return {
                "isochrone": data,
                "center": {"lon": lon, "lat": lat},
                "minutes": contours_minutes,
                "profile": profile
            }
    
    except httpx.HTTPError as e:
        return {"error": f"Isochrone failed: {str(e)}"}


@router.post("/matrix")
async def get_travel_matrix(request: MatrixRequest):
    """
    Matrix API: Calculate all-to-all travel times and distances
    
    Args:
        request: MatrixRequest with coordinates and profile
    
    Returns:
        Travel time and distance matrix
    """
    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return {"error": "Mapbox token not configured"}
    
    if len(request.coordinates) > 25:
        return {"error": "Maximum 25 coordinates allowed"}
    
    try:
        # Format: lon1,lat1;lon2,lat2;...
        coords_str = ";".join([f"{c['lon']},{c['lat']}" for c in request.coordinates])
        url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/{request.profile}/{coords_str}"
        params = {
            "annotations": "duration,distance",
            "access_token": mapbox_token
        }
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return {"error": f"Matrix API failed: status {response.status_code}", "details": response.text}
            data = response.json()
            
            return {
                "durations": data.get("durations", []),  # seconds
                "distances": data.get("distances", []),  # meters
                "sources": request.coordinates,
                "destinations": request.coordinates
            }
    
    except httpx.HTTPError as e:
        return {"error": f"Matrix API failed: {str(e)}"}


@router.post("/map-matching")
async def map_match_gps(request: MapMatchingRequest):
    """
    Map Matching API: Snap GPS traces to road network
    
    Args:
        request: MapMatchingRequest with coordinates and optional timestamps
    
    Returns:
        Matched route on road network with speed estimates
    """
    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return {"error": "Mapbox token not configured"}
    
    if len(request.coordinates) > 100:
        return {"error": "Maximum 100 coordinates allowed"}
    
    try:
        # Format: lon1,lat1;lon2,lat2;...
        coords_str = ";".join([f"{c['lon']},{c['lat']}" for c in request.coordinates])
        url = f"https://api.mapbox.com/matching/v5/mapbox/driving/{coords_str}"
        params = {
            "geometries": "geojson",
            "overview": "full",
            "annotations": "speed,duration,distance",
            "access_token": mapbox_token
        }
        
        if request.timestamps:
            # Format: timestamp1;timestamp2;...
            params["timestamps"] = ";".join(request.timestamps)
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return {"error": f"Map matching failed: status {response.status_code}", "details": response.text}
            data = response.json()
            
            if data.get("matchings"):
                matching = data["matchings"][0]
                return {
                    "matched_route": matching["geometry"],
                    "distance": matching["distance"],  # meters
                    "duration": matching["duration"],  # seconds
                    "confidence": matching.get("confidence", 0),
                    "speeds": matching.get("legs", [{}])[0].get("annotation", {}).get("speed", [])
                }
            else:
                return {"error": "No matching found"}
    
    except httpx.HTTPError as e:
        return {"error": f"Map matching failed: {str(e)}"}


@router.post("/recommend")
async def recommend_routes(payload: RouteAnalyzeRequest, db: Session = Depends(get_db)):
    """
    Recommendation endpoint that uses Mapbox Directions API to get alternative routes.
    Returns up to 3 alternative routes with real road-following geometry.
    """
    # Get Mapbox access token from environment
    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN')
    
    if not mapbox_token:
        # Fallback to mock if no Mapbox token
        return _generate_mock_alternatives(payload)
    
    # Build coordinate list for Mapbox
    coords = [[payload.start_lon, payload.start_lat]]
    if payload.waypoints:
        coords.extend([[wp['lon'], wp['lat']] for wp in payload.waypoints])
    coords.append([payload.end_lon, payload.end_lat])
    
    # Format coordinates for Mapbox: "lon,lat;lon,lat;..."
    coordinates_str = ";".join([f"{c[0]},{c[1]}" for c in coords])
    
    # Call Mapbox Directions API with alternatives - use driving-traffic profile for real-time traffic
    mapbox_url = f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/{coordinates_str}"
    params = {
        'access_token': mapbox_token,
        'alternatives': 'true',
        'geometries': 'geojson',
        'overview': 'full',
        'steps': 'false'
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(mapbox_url, params=params)
            if response.status_code != 200:
                return {
                    "error": f"Directions failed: status {response.status_code}",
                    "details": response.text,
                    "routes": []
                }
            data = response.json()
        
        if 'routes' not in data or not data['routes']:
            return _generate_mock_alternatives(payload)
        
        routes = []
        for i, route in enumerate(data['routes'][:3]):  # Limit to 3 routes
            geometry = route.get('geometry', {})
            route_coords = geometry.get('coordinates', [])
            
            # Distance in meters, convert to km
            distance_m = route.get('distance', 0)
            distance_km = round(distance_m / 1000, 4)
            
            # Duration in seconds, convert to minutes
            duration_s = route.get('duration', 0)
            travel_time_min = max(1, int(duration_s / 60))
            
            # Calculate traffic score (normalized inverse of duration)
            traffic_score = round(1.0 / (1.0 + duration_s / 3600), 3)
            
            # Estimate emissions based on distance
            emission_g = max(50, int(distance_km * 120))
            
            routes.append({
                "id": f"mapbox-{i+1}",
                "name": f"Route {i+1}" if len(data['routes']) > 1 else "Main Route",
                "coordinates": route_coords,
                "distance_km": distance_km,
                "travel_time_min": travel_time_min,
                "traffic_score": traffic_score,
                "emission_g": emission_g,
                "rank": i + 1
            })
        
        return {"routes": routes}
    
    except Exception as e:
        # Fallback to mock on any error
        print(f"Mapbox API error: {e}")
        return _generate_mock_alternatives(payload)


def _generate_mock_alternatives(payload: RouteAnalyzeRequest):
    """Generate mock alternatives when Mapbox is unavailable."""
    coords = [[payload.start_lon, payload.start_lat]]
    if payload.waypoints:
        coords.extend([[wp['lon'], wp['lat']] for wp in payload.waypoints])
    coords.append([payload.end_lon, payload.end_lat])
    
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


@router.post("/optimize")
async def optimize_route(request: OptimizationRequest):
    """
    Optimization API: Solve multi-stop routing problem (TSP)
    
    Args:
        request: OptimizationRequest with stops, source, destination, roundtrip
    
    Returns:
        Optimized route with best stop order
    """
    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return {"error": "Mapbox token not configured"}
    
    if len(request.coordinates) < 2:
        return {"error": "At least 2 stops required"}
    
    if len(request.coordinates) > 12:
        return {"error": "Maximum 12 stops allowed"}
    
    try:
        # Format coordinates: lon1,lat1;lon2,lat2;...
        coords_str = ";".join([f"{stop.lon},{stop.lat}" for stop in request.coordinates])
        
        url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/{request.profile}/{coords_str}"
        params = {
            "access_token": mapbox_token,
            "source": request.source,
            "destination": request.destination,
            "roundtrip": str(request.roundtrip).lower(),
            "geometries": "geojson",
            "overview": "full"
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return {"error": f"Optimization failed: status {response.status_code}", "details": response.text}
            data = response.json()
            
            if "trips" not in data or not data["trips"]:
                return {"error": "No optimal route found"}
            
            trip = data["trips"][0]
            
            # Extract optimized order
            waypoint_order = [wp["waypoint_index"] for wp in data.get("waypoints", [])]
            optimized_stops = [request.coordinates[i] for i in waypoint_order]
            
            # Calculate savings vs unoptimized
            duration = trip["duration"]  # seconds
            distance = trip["distance"]  # meters
            
            return {
                "optimized_route": {
                    "geometry": trip["geometry"],
                    "distance_km": round(distance / 1000, 2),
                    "duration_min": round(duration / 60, 1),
                    "stops": [
                        {
                            "order": i + 1,
                            "name": stop.name or f"Stop {i + 1}",
                            "lon": stop.lon,
                            "lat": stop.lat
                        }
                        for i, stop in enumerate(optimized_stops)
                    ]
                },
                "original_order": [
                    {"name": stop.name or f"Stop {i + 1}", "lon": stop.lon, "lat": stop.lat}
                    for i, stop in enumerate(request.coordinates)
                ],
                "waypoint_order": waypoint_order,
                "summary": {
                    "total_distance_km": round(distance / 1000, 2),
                    "total_duration_min": round(duration / 60, 1),
                    "num_stops": len(request.coordinates),
                    "profile": request.profile,
                    "roundtrip": request.roundtrip
                }
            }
    
    except httpx.HTTPError as e:
        return {"error": f"Optimization failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@router.post("/static-image")
async def generate_static_image(
    center_lon: float,
    center_lat: float,
    zoom: int = 14,
    width: int = 800,
    height: int = 600,
    markers: Optional[List[Dict[str, float]]] = None
):
    """
    Static Images API: Generate map snapshot
    
    Args:
        center_lon: Center longitude
        center_lat: Center latitude
        zoom: Zoom level (0-22)
        width: Image width in pixels
        height: Image height in pixels
        markers: Optional list of marker positions
    
    Returns:
        URL to generated static map image
    """
    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return {"error": "Mapbox token not configured"}
    
    try:
        # Build markers overlay
        overlay = ""
        if markers:
            marker_strs = []
            for i, marker in enumerate(markers[:10]):  # Max 10 markers
                # pin-s-{label}+{color}(lon,lat)
                label = chr(97 + i) if i < 26 else str(i)  # a, b, c, ... or numbers
                color = "FF0000" if i == 0 else "0000FF"
                marker_strs.append(f"pin-s-{label}+{color}({marker['lon']},{marker['lat']})")
            overlay = ",".join(marker_strs) + "/"
        
        # Construct Static Images API URL
        # Format: /styles/v1/{username}/{style_id}/static/{overlay}{lon},{lat},{zoom}/{width}x{height}{@2x}
        url = (
            f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/"
            f"{overlay}{center_lon},{center_lat},{zoom}/{width}x{height}@2x"
            f"?access_token={mapbox_token}"
        )
        
        return {
            "image_url": url,
            "center": {"lon": center_lon, "lat": center_lat},
            "zoom": zoom,
            "dimensions": {"width": width, "height": height},
            "markers_count": len(markers) if markers else 0
        }
    
    except Exception as e:
        return {"error": f"Image generation failed: {str(e)}"}
