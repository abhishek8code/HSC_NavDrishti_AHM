from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import db_config, models
from .auth import get_current_user, require_role, get_db
from sqlalchemy.orm import Session
from .routers.projects import router as projects_router
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
import networkx as nx
from typing import List, Dict, Optional, Tuple
import json
import io
from pydantic import BaseModel

app = FastAPI(title="Damaged Roads Service", version="1.0.0")

# Global variables to store road network data
road_network_gdf: Optional[gpd.GeoDataFrame] = None
road_network_graph: Optional[nx.DiGraph] = None
damaged_roads_df: Optional[pd.DataFrame] = None  # Store ingested damaged roads data

# Tolerance for snapping GPS points (in degrees)
SNAP_TOLERANCE = 0.0001


class DamagedRoadPoint(BaseModel):
    """Model for a damaged road point"""
    lat: float
    lon: float
    severity: str


class SnappedPoint(BaseModel):
    """Model for a snapped point result"""
    original_lat: float
    original_lon: float
    snapped_lat: float
    snapped_lon: float
    severity: str
    distance: float
    road_segment_id: Optional[int] = None


def snap_point_to_linestring(
    point: Point,
    road_network: gpd.GeoDataFrame,
    tolerance: float = SNAP_TOLERANCE
) -> Tuple[Optional[Point], float, Optional[int]]:
    """
    Snap a GPS point to the nearest LineString in the road network.
    
    Args:
        point: Shapely Point object (lon, lat)
        road_network: GeoDataFrame containing LineString geometries
        tolerance: Maximum distance in degrees to snap (default: 0.0001)
    
    Returns:
        Tuple of (snapped_point, distance, road_segment_id)
        Returns None for snapped_point if no road is within tolerance
    """
    if road_network is None or len(road_network) == 0:
        raise ValueError("Road network not loaded. Please upload a GeoJSON file first.")
    
    min_distance = float('inf')
    nearest_point = None
    nearest_segment_id = None
    
    # Iterate through all road segments
    for idx, row in road_network.iterrows():
        road_geometry = row.geometry
        
        if isinstance(road_geometry, LineString):
            # Find the nearest point on this LineString
            nearest_on_line, _ = nearest_points(road_geometry, point)
            distance = point.distance(nearest_on_line)
            
            # Check if this is the closest so far and within tolerance
            if distance < min_distance:
                min_distance = distance
                nearest_point = nearest_on_line
                nearest_segment_id = idx
    
    # Check if the nearest point is within tolerance
    if min_distance <= tolerance:
        return nearest_point, min_distance, nearest_segment_id
    else:
        return None, min_distance, None


def initialize_networkx_graph(road_network: gpd.GeoDataFrame) -> nx.DiGraph:
    """
    Initialize a NetworkX DiGraph (Directed Graph) from road network GeoJSON data.
    
    Args:
        road_network: GeoDataFrame containing LineString geometries
    
    Returns:
        NetworkX DiGraph representing the road network
    """
    if road_network is None or len(road_network) == 0:
        raise ValueError("Road network not loaded. Please upload a GeoJSON file first.")
    
    G = nx.DiGraph()
    
    # Process each road segment
    for idx, row in road_network.iterrows():
        geometry = row.geometry
        
        if isinstance(geometry, LineString):
            coords = list(geometry.coords)
            
            # Add nodes (intersections/endpoints)
            for coord in coords:
                node_id = (round(coord[0], 6), round(coord[1], 6))  # Use rounded coordinates as node ID
                if not G.has_node(node_id):
                    G.add_node(node_id, lat=coord[1], lon=coord[0])
            
            # Add edges (road segments)
            for i in range(len(coords) - 1):
                start_node = (round(coords[i][0], 6), round(coords[i][1], 6))
                end_node = (round(coords[i+1][0], 6), round(coords[i+1][1], 6))
                
                # Calculate edge weight (distance in degrees, can be converted to meters)
                edge_length = Point(coords[i]).distance(Point(coords[i+1]))
                
                # Add edge with attributes
                edge_attrs = {
                    'length': edge_length,
                    'segment_id': idx,
                    'geometry': LineString([coords[i], coords[i+1]])
                }
                
                # Add both directions for undirected roads (or just one for directed)
                G.add_edge(start_node, end_node, **edge_attrs)
                # Uncomment below if roads are bidirectional
                # G.add_edge(end_node, start_node, **edge_attrs)
    
    return G


@app.post("/upload-road-network")
async def upload_road_network(file: UploadFile = File(...), user=Depends(require_role("admin"))):
    """
    Upload and load a GeoJSON road network file.
    This initializes the road network GeoDataFrame and NetworkX graph.
    """
    global road_network_gdf, road_network_graph
    
    if not file.filename.endswith(('.geojson', '.json')):
        raise HTTPException(status_code=400, detail="File must be a GeoJSON file")
    
    try:
        # Read the uploaded file
        contents = await file.read()
        road_network_gdf = gpd.read_file(io.BytesIO(contents))
        
        # Validate that geometries are LineStrings
        if not all(isinstance(geom, LineString) for geom in road_network_gdf.geometry):
            raise HTTPException(
                status_code=400,
                detail="Road network must contain LineString geometries"
            )
        
        # Initialize NetworkX graph
        road_network_graph = initialize_networkx_graph(road_network_gdf)
        
        return {
            "message": "Road network loaded successfully",
            "num_segments": len(road_network_gdf),
            "num_nodes": road_network_graph.number_of_nodes(),
            "num_edges": road_network_graph.number_of_edges()
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error loading road network: {str(e)}")


@app.post("/ingest-damaged-roads")
async def ingest_damaged_roads(file: UploadFile = File(...), user=Depends(require_role("admin"))):
    """
    Ingest a CSV file containing damaged roads data (Lat, Lon, Severity).
    Snaps each GPS point to the nearest road segment in the loaded network.
    Admin-only endpoint.
    """
    global road_network_gdf
    
    if road_network_gdf is None:
        raise HTTPException(
            status_code=400,
            detail="Road network not loaded. Please upload a GeoJSON file first using /upload-road-network"
        )
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    try:
        # Read CSV file
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Store the original dataframe for evidence image retrieval
        damaged_roads_df = df.copy()
        
        # Normalize column names (handle both 'Lat'/'Latitude' and 'Lon'/'Longitude')
        if 'Latitude' in df.columns:
            df['Lat'] = df['Latitude']
        if 'Longitude' in df.columns:
            df['Lon'] = df['Longitude']
        if 'Image_URL' in df.columns:
            df['EvidenceImageUrl'] = df['Image_URL']
        elif 'EvidenceImageUrl' not in df.columns:
            df['EvidenceImageUrl'] = None
        
        # Validate required columns
        required_columns = ['Lat', 'Lon', 'Severity']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"CSV must contain columns: {required_columns}. Missing: {missing_columns}"
            )
        
        # Process each damaged road point
        snapped_results = []
        for _, row in df.iterrows():
            lat = float(row['Lat'])
            lon = float(row['Lon'])
            severity = str(row['Severity'])
            
            # Create Point geometry (note: shapely uses lon, lat order)
            point = Point(lon, lat)
            
            # Snap to nearest road segment
            snapped_point, distance, segment_id = snap_point_to_linestring(
                point, road_network_gdf, SNAP_TOLERANCE
            )
            
            if snapped_point:
                snapped_results.append({
                    "original_lat": lat,
                    "original_lon": lon,
                    "snapped_lat": snapped_point.y,
                    "snapped_lon": snapped_point.x,
                    "severity": severity,
                    "distance": distance,
                    "road_segment_id": int(segment_id) if segment_id is not None else None
                })
            else:
                # Point is outside tolerance
                snapped_results.append({
                    "original_lat": lat,
                    "original_lon": lon,
                    "snapped_lat": None,
                    "snapped_lon": None,
                    "severity": severity,
                    "distance": distance,
                    "road_segment_id": None,
                    "warning": f"Point is {distance:.6f} degrees away from nearest road (tolerance: {SNAP_TOLERANCE})"
                })
        
        return {
            "message": f"Processed {len(df)} damaged road points",
            "successfully_snapped": sum(1 for r in snapped_results if r.get("snapped_lat") is not None),
            "outside_tolerance": sum(1 for r in snapped_results if r.get("snapped_lat") is None),
            "results": snapped_results
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing damaged roads CSV: {str(e)}")


@app.get("/road-network-status")
async def get_road_network_status():
    """Get the status of the loaded road network and graph."""
    global road_network_gdf, road_network_graph
    
    if road_network_gdf is None:
        return {
            "road_network_loaded": False,
            "graph_initialized": False
        }
    
    return {
        "road_network_loaded": True,
        "graph_initialized": road_network_graph is not None,
        "num_segments": len(road_network_gdf),
        "num_nodes": road_network_graph.number_of_nodes() if road_network_graph else 0,
        "num_edges": road_network_graph.number_of_edges() if road_network_graph else 0
    }


@app.get("/cluster-evidence-images")
async def get_cluster_evidence_images(
    lat: float,
    lon: float,
    radius_degrees: float = 0.001
):
    """
    Get evidence images for a cluster/red zone at the given coordinates.
    Returns all images within the specified radius that contributed to the cluster.
    
    Args:
        lat: Latitude of the cluster center
        lon: Longitude of the cluster center
        radius_degrees: Search radius in degrees (default: 0.001, approximately 111 meters)
    
    Returns:
        List of evidence images with metadata
    """
    global damaged_roads_df
    
    if damaged_roads_df is None:
        raise HTTPException(
            status_code=400,
            detail="No damaged roads data loaded. Please upload a CSV file first."
        )
    
    try:
        # Normalize column names
        df = damaged_roads_df.copy()
        if 'Latitude' in df.columns:
            df['Lat'] = df['Latitude']
        if 'Longitude' in df.columns:
            df['Lon'] = df['Longitude']
        if 'Image_URL' in df.columns:
            df['EvidenceImageUrl'] = df['Image_URL']
        
        # Filter points within radius
        lat_min = lat - radius_degrees
        lat_max = lat + radius_degrees
        lon_min = lon - radius_degrees
        lon_max = lon + radius_degrees
        
        nearby_points = df[
            (df['Lat'] >= lat_min) & (df['Lat'] <= lat_max) &
            (df['Lon'] >= lon_min) & (df['Lon'] <= lon_max)
        ].copy()
        
        # Calculate distance for each point (simple Euclidean for filtering)
        nearby_points['distance'] = (
            ((nearby_points['Lat'] - lat) ** 2 + (nearby_points['Lon'] - lon) ** 2) ** 0.5
        )
        
        # Filter by actual radius
        nearby_points = nearby_points[nearby_points['distance'] <= radius_degrees]
        
        # Extract evidence images
        evidence_images = []
        for _, row in nearby_points.iterrows():
            image_url = row.get('EvidenceImageUrl') or row.get('Image_URL')
            if pd.notna(image_url) and str(image_url).strip():
                evidence_images.append({
                    "image_url": str(image_url).strip(),
                    "latitude": float(row['Lat']),
                    "longitude": float(row['Lon']),
                    "severity": float(row['Severity']) if pd.notna(row.get('Severity')) else None,
                    "distance": float(row['distance'])
                })
        
        return {
            "cluster_center": {"lat": lat, "lon": lon},
            "radius_degrees": radius_degrees,
            "total_images": len(evidence_images),
            "images": evidence_images
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving evidence images: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Damaged Roads Service",
        "version": "1.0.0",
        "endpoints": {
            "POST /upload-road-network": "Upload GeoJSON road network file",
            "POST /ingest-damaged-roads": "Upload CSV file with damaged roads (Lat, Lon, Severity)",
            "GET /road-network-status": "Get status of loaded road network",
            "GET /cluster-evidence-images": "Get evidence images for a cluster/red zone",
            "GET /": "API information"
        }
    }

# Include routers

# auth routes are provided in the routers/auth.py router
from .routers.auth import router as auth_router
from .routers.routes import router as routes_router
from .routers.traffic import router as traffic_router
from .routers.notifications import router as notifications_router
from .routers.users import router as users_router
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(routes_router)
app.include_router(traffic_router)
app.include_router(notifications_router)
app.include_router(users_router)

