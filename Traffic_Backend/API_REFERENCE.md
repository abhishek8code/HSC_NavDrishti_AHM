# Traffic & Road Construction Management System - API Reference

**Version:** 1.0  
**Date:** November 29, 2025  
**Backend Framework:** FastAPI (Python)  
**Database:** SQLite (dev fallback) / MySQL 8.0+  

---

## API Overview

The backend API provides RESTful endpoints for project management, route analysis, traffic monitoring, notifications, and user management. All endpoints use JSON for request/response bodies unless otherwise noted.

### Base URL
```
http://localhost:8000
```

### Authentication
- **Token-based**: JWT via `/auth/token` endpoint
- **Session timeout**: 30 minutes of inactivity
- **Required header for protected endpoints**: `Authorization: Bearer <token>`

---

## Endpoints by Functional Area

### 1. Authentication (FR-3.10, NFR-5.3)

#### Register a new user
```http
POST /auth/register
Content-Type: application/json

{
  "username": "string (3-64 chars)",
  "email": "string",
  "password": "string (min 8 chars, mixed case + symbols)"
}

Response 201:
{
  "id": 1,
  "username": "string",
  "email": "string"
}
```

#### Login and get token
```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=user&password=pass

Response 200:
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### 2. Project Management (FR-3.1, FR-3.10)

#### Create a new project
```http
POST /projects/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "string (3-128 chars)",
  "status": "planned|active|completed|cancelled",
  "start_time": "2025-01-15T10:00:00",
  "end_time": "2025-01-20T16:00:00",
  "start_lat": 28.6139,
  "start_lon": 77.2090,
  "end_lat": 28.6200,
  "end_lon": 77.2200,
  "resource_allocation": "string",
  "emission_reduction_estimate": 100.5
}

Response 201:
{
  "id": 1,
  "name": "string",
  "status": "planned"
}
```
**Access:** Admin role required

#### List all projects
```http
GET /projects/
Authorization: Bearer <token>

Response 200:
[
  {
    "id": 1,
    "name": "string",
    "status": "planned"
  }
]
```

#### Get project details
```http
GET /projects/{project_id}
Authorization: Bearer <token>

Response 200:
{
  "id": 1,
  "name": "string",
  "status": "planned"
}
```

#### Update project
```http
PUT /projects/{project_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "string (optional)",
  "status": "active|completed|cancelled (optional)",
  "start_time": "ISO8601 (optional)",
  "end_time": "ISO8601 (optional)"
}

Response 200:
{
  "id": 1,
  "name": "updated name",
  "status": "active"
}
```
**Access:** Admin role required

#### Delete project
```http
DELETE /projects/{project_id}
Authorization: Bearer <token>

Response 204: No Content
```
**Access:** Admin role required

---

### 3. Route Analysis & Recommendations (FR-3.2, FR-3.3, FR-3.4)

#### Analyze a route
```http
POST /routes/analyze
Authorization: Bearer <token>
Content-Type: application/json

{
  "coordinates": [[77.2090, 28.6139], [77.2200, 28.6200]]
}

Response 200:
{
  "length_degrees": 0.0125,
  "num_segments": 1,
  "approximate_length_km": 1.39
}
```

#### Get route metrics
```http
GET /routes/{route_id}/metrics
Authorization: Bearer <token>

Response 200:
{
  "route_id": 1,
  "segment_name": "Main Road",
  "base_capacity": 5000,
  "vehicle_count_sum": 1200,
  "average_speed": 45.5
}
```

#### Get alternative routes
```http
GET /routes/{route_id}/alternatives?start_lon=77.2090&start_lat=28.6139&end_lon=77.2200&end_lat=28.6200
Authorization: Bearer <token>

Response 200:
{
  "route_id": 1,
  "alternatives": [
    {
      "route_id": 0,
      "length_km": 1.39,
      "num_segments": 2,
      "suitability_score": 0.417,
      "rank": 1
    }
  ]
}
```

#### Get route recommendation
```http
POST /routes/{route_id}/recommend?start_lon=77.2090&start_lat=28.6139&end_lon=77.2200&end_lat=28.6200
Authorization: Bearer <token>

Response 200:
{
  "route_id": 1,
  "recommended_alternative_id": 0,
  "all_alternatives": [
    {
      "route_id": 0,
      "length_km": 1.39,
      "num_segments": 2,
      "suitability_score": 0.417,
      "rank": 1
    }
  ],
  "recommendation_justification": "Route 0 recommended: length 1.39 km, score 0.4167"
}
```

---

### 4. Traffic Monitoring (FR-3.9)

#### Get live traffic
```http
GET /traffic/live/{route_id}
Authorization: Bearer <token>

Response 200:
{
  "route_id": 1,
  "timestamp": "2025-01-15T10:30:00",
  "vehicle_count": 850,
  "average_speed": 35.2,
  "congestion_state": "moderate"
}
```

#### Get traffic history
```http
GET /traffic/history/{route_id}?limit=50
Authorization: Bearer <token>

Response 200:
{
  "route_id": 1,
  "count": 50,
  "entries": [
    {
      "timestamp": "2025-01-15T10:30:00",
      "vehicle_count": 850,
      "avg_speed": 35.2,
      "congestion_state": "moderate"
    }
  ]
}
```

#### Configure traffic threshold
```http
POST /traffic/threshold/configure
Authorization: Bearer <token>
Content-Type: application/json

{
  "route_id": 1,
  "vehicle_count_limit": 2000,
  "density_limit": 0.8
}

Response 200:
{
  "road_segment_id": 1,
  "configured": true
}
```
**Access:** Admin role required

#### Get traffic threshold
```http
GET /traffic/threshold/{route_id}
Authorization: Bearer <token>

Response 200:
{
  "road_segment_id": 1,
  "threshold": {
    "vehicle_count_limit": 2000,
    "density_limit": 0.8
  }
}
```

---

### 5. Notifications (FR-3.8)

#### Send notification
```http
POST /notifications/send
Authorization: Bearer <token>
Content-Type: application/json

{
  "project_id": 1,
  "recipient_type": "admin|public",
  "message": "string",
  "template": "default_admin"
}

Response 200:
{
  "sent": true,
  "notification_id": 1,
  "timestamp": "2025-01-15T10:30:00Z"
}
```
**Access:** Admin role required

#### Get notification log
```http
GET /notifications/log?limit=100
Authorization: Bearer <token>

Response 200:
{
  "total": 42,
  "entries": [
    {
      "id": 42,
      "project_id": 1,
      "recipient_type": "admin",
      "message": "Project 1 completed successfully",
      "timestamp": "2025-01-15T10:30:00",
      "status": "sent"
    }
  ]
}
```

#### Get notification templates
```http
GET /notifications/templates
Authorization: Bearer <token>

Response 200:
{
  "templates": {
    "default_admin": "Project {project_id} requires approval.",
    "public_update": "Construction update for project {project_id}: {message}"
  }
}
```

---

### 6. User Management (FR-3.10)

#### Get user details
```http
GET /users/{user_id}
Authorization: Bearer <token>

Response 200:
{
  "id": 1,
  "username": "officer1",
  "email": "officer1@example.com"
}
```

#### Update user profile
```http
PUT /users/{user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "email": "newemail@example.com",
  "is_active": 1
}

Response 200:
{
  "id": 1,
  "username": "officer1",
  "email": "newemail@example.com"
}
```

---

### 7. Road Network & Damage Analysis

#### Upload road network (GeoJSON)
```http
POST /upload-road-network
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=<road_network.geojson>

Response 200:
{
  "message": "Road network loaded successfully",
  "num_segments": 150,
  "num_nodes": 320,
  "num_edges": 1200
}
```
**Access:** Admin role required

#### Ingest damaged roads (CSV)
```http
POST /ingest-damaged-roads
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=<damaged_roads.csv>

Response 200:
{
  "message": "Processed 500 damaged road points",
  "successfully_snapped": 485,
  "outside_tolerance": 15,
  "results": [...]
}
```
**Access:** Admin role required

#### Get evidence images for cluster
```http
GET /cluster-evidence-images?lat=28.6139&lon=77.2090&radius_degrees=0.001
Authorization: Bearer <token>

Response 200:
{
  "cluster_center": {"lat": 28.6139, "lon": 77.2090},
  "radius_degrees": 0.001,
  "total_images": 5,
  "images": [
    {
      "image_url": "https://...",
      "latitude": 28.6140,
      "longitude": 77.2091,
      "severity": 7.5,
      "distance": 0.00008
    }
  ]
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created successfully |
| 204 | No Content - Request succeeded with no response body (DELETE) |
| 400 | Bad Request - Invalid request parameters or body |
| 401 | Unauthorized - Missing or invalid authentication token |
| 403 | Forbidden - Authenticated but lacks required role/permission |
| 404 | Not Found - Resource does not exist |
| 422 | Unprocessable Entity - Validation error in request body |
| 500 | Internal Server Error - Server error |

---

## SRS Requirement Mapping

| SRS Requirement | Endpoint(s) | Status |
|-----------------|-------------|--------|
| FR-3.1: Project Dashboard | GET /projects/, GET /projects/{id} | ✅ Implemented |
| FR-3.2: Route Selection & Analysis | POST /routes/analyze, GET /routes/{id}/metrics | ✅ Implemented |
| FR-3.3: Alternative Route Identification | GET /routes/{id}/alternatives | ✅ Implemented |
| FR-3.4: Route Recommendation Engine | POST /routes/{id}/recommend | ✅ Implemented |
| FR-3.5: Lane-Specific Analysis | (requires detailed schema) | ⏳ Pending |
| FR-3.6: Diversion & Expansion Planning | (requires dedicated endpoint) | ⏳ Pending |
| FR-3.7: Traffic Management Strategy Selection | (integrated with projects) | ⏳ Pending |
| FR-3.8: Notification System | POST /notifications/send, GET /notifications/log | ✅ Implemented |
| FR-3.9: Real-time Traffic Monitoring | GET /traffic/live/{id}, GET /traffic/history/{id} | ✅ Implemented |
| FR-3.10: Project Creation & Management | POST/GET/PUT/DELETE /projects | ✅ Implemented |
| FR-3.11: Scenario Differentiation | (metadata in project/route) | ⏳ Pending |
| NFR-5.3: RBAC & Security | require_role() on sensitive endpoints | ✅ Implemented |

---

## Quick Start

### 1. Register a user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "officer1", "email": "officer@example.com", "password": "SecurePass123!"}'
```

### 2. Get authentication token
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=officer1&password=SecurePass123!"
```

### 3. Create a project (with token)
```bash
TOKEN="<token_from_step_2>"
curl -X POST http://localhost:8000/projects/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Highway Repair Project", "status": "planned"}'
```

### 4. Analyze a route
```bash
curl -X POST http://localhost:8000/routes/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"coordinates": [[77.2090, 28.6139], [77.2200, 28.6200]]}'
```

---

## Notes & Future Work

- **Graph-based routing** is implemented using NetworkX; shortest-path alternatives are returned and scored.
- **Notification persistence** uses SQLite/MySQL backing; in-memory storage has been replaced with DB tables.
- **Traffic thresholds** are now persisted in the DB and can be queried/configured per road segment.
- **Role-based access** is enforced via `require_role("admin")` decorators on sensitive endpoints.
- **Alembic migrations** are tracked in `Traffic_Backend/alembic/versions/` for versioning schema changes.

---

## Support

For issues or questions about the API, consult the SRS_SUMMARY.md document or open a GitHub issue.

