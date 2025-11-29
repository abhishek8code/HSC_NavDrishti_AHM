# Traffic & Road Construction Management System - Quick Start Guide

**Last Updated:** November 29, 2025

---

## 5-Minute Setup

### Prerequisites
- Python 3.11+
- Git
- (Optional) MySQL 8.0+ or use SQLite fallback

### 1. Clone and Install Dependencies

```bash
cd c:\Users\abhis\HSC_NavDrishti_AHM
pip install -r Traffic_Backend/requirements.txt
```

### 2. Initialize Database

```bash
cd Traffic_Backend
python init_db.py
```

This will:
- Create tables (SQLite at `dev_navdrishti.db` if MySQL unavailable)
- Seed sample projects
- Create admin user: `admin` / `adminpass`

### 3. Start Backend Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or from repo root:

```bash
python -m uvicorn Traffic_Backend.main:app --reload --host 0.0.0.0 --port 8000
```

Backend is now running at `http://localhost:8000`

---

## API Quickstart

### Step 1: Get Authentication Token

```bash
# Login with admin credentials
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=adminpass"
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

Save the token as `TOKEN`:
```bash
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### Step 2: Create a Project

```bash
curl -X POST http://localhost:8000/projects/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main Road Construction",
    "status": "planned",
    "start_lat": 28.6139,
    "start_lon": 77.2090,
    "end_lat": 28.6200,
    "end_lon": 77.2200
  }'
```

Response:
```json
{
  "id": 1,
  "name": "Main Road Construction",
  "status": "planned"
}
```

### Step 3: List All Projects

```bash
curl -X GET http://localhost:8000/projects/ \
  -H "Authorization: Bearer $TOKEN"
```

### Step 4: Analyze a Route

```bash
curl -X POST http://localhost:8000/routes/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "coordinates": [
      [77.2090, 28.6139],
      [77.2110, 28.6150],
      [77.2200, 28.6200]
    ]
  }'
```

Response:
```json
{
  "length_degrees": 0.0125,
  "num_segments": 2,
  "approximate_length_km": 1.39
}
```

### Step 5: Get Alternative Routes

```bash
curl -X GET "http://localhost:8000/routes/1/alternatives?start_lon=77.2090&start_lat=28.6139&end_lon=77.2200&end_lat=28.6200" \
  -H "Authorization: Bearer $TOKEN"
```

Note: Road network must be loaded first via `/upload-road-network` endpoint to get alternatives.

### Step 6: Send a Notification

```bash
curl -X POST http://localhost:8000/notifications/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "recipient_type": "admin",
    "message": "Project 1 is ready for review",
    "template": "default_admin"
  }'
```

### Step 7: Get Notification Log

```bash
curl -X GET http://localhost:8000/notifications/log \
  -H "Authorization: Bearer $TOKEN"
```

---

## Running Tests

```bash
# Run all tests
python -m pytest -q

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest Traffic_Backend/tests/test_auth_and_projects.py -v

# Run with coverage report
python -m pytest --cov=Traffic_Backend
```

**Expected Result:** 19 tests passing ✅

---

## Common Workflows

### Workflow 1: Create Project and Analyze Route

```bash
# 1. Register user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "officer1",
    "email": "officer1@example.com",
    "password": "SecurePassword123!"
  }'

# 2. Get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=officer1&password=SecurePassword123!" | jq -r '.access_token')

# 3. Create project
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Highway Repair",
    "status": "planned",
    "start_lat": 28.6139,
    "start_lon": 77.2090,
    "end_lat": 28.6200,
    "end_lon": 77.2200
  }' | jq -r '.id')

echo "Created project: $PROJECT_ID"

# 4. Analyze route
curl -s -X POST http://localhost:8000/routes/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "coordinates": [
      [77.2090, 28.6139],
      [77.2200, 28.6200]
    ]
  }' | jq '.'
```

### Workflow 2: Configure Traffic Monitoring

```bash
# Configure threshold for road segment 1
curl -X POST http://localhost:8000/traffic/threshold/configure \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": 1,
    "vehicle_count_limit": 2000,
    "density_limit": 0.8
  }'

# Get live traffic
curl -X GET http://localhost:8000/traffic/live/1 \
  -H "Authorization: Bearer $TOKEN"

# Get traffic history
curl -X GET http://localhost:8000/traffic/history/1?limit=50 \
  -H "Authorization: Bearer $TOKEN"
```

### Workflow 3: Load Road Network and Get Recommendations

```bash
# 1. Upload GeoJSON road network (requires GeoJSON file)
curl -X POST http://localhost:8000/upload-road-network \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@road_network.geojson"

# 2. Get alternative routes
curl -X GET "http://localhost:8000/routes/1/alternatives?start_lon=77.2090&start_lat=28.6139&end_lon=77.2200&end_lat=28.6200" \
  -H "Authorization: Bearer $TOKEN"

# 3. Get recommendation
curl -X POST "http://localhost:8000/routes/1/recommend?start_lon=77.2090&start_lat=28.6139&end_lon=77.2200&end_lat=28.6200" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Debugging

### Check API Health

```bash
curl http://localhost:8000/
```

### View Interactive API Docs

```
http://localhost:8000/docs
```

(Swagger UI - login with credentials to test endpoints)

### Run Debug Script

```bash
python Traffic_Backend/run_debug_sequence.py
```

This reproduces the full workflow: register, login, create project, update project.

### Check Database

```bash
# List all projects
sqlite3 dev_navdrishti.db "SELECT * FROM projects;"

# List all users
sqlite3 dev_navdrishti.db "SELECT id, username, email, roles FROM users;"

# List notifications
sqlite3 dev_navdrishti.db "SELECT * FROM notifications LIMIT 10;"
```

---

## Configuration

### Database Selection

**Default:** SQLite at `dev_navdrishti.db`

**Use MySQL:** Set environment variable before starting server

```bash
# Windows PowerShell
$env:DATABASE_URL = "mysql+pymysql://username:password@localhost/navdrishti"
python -m uvicorn Traffic_Backend.main:app --reload

# Linux/Mac bash
export DATABASE_URL="mysql+pymysql://username:password@localhost/navdrishti"
python -m uvicorn Traffic_Backend.main:app --reload
```

### JWT Secret (Production)

```bash
# Generate random key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set environment variable
$env:JWT_SECRET_KEY = "<your-generated-key>"
```

### Session Timeout

Default: 30 minutes of inactivity (configured in `auth.py`)

---

## Useful Commands

### Run Backend in Production Mode

```bash
gunicorn -w 4 -b 0.0.0.0:8000 Traffic_Backend.main:app
```

### Generate Alembic Migration

```bash
cd Traffic_Backend
alembic revision --autogenerate -m "Add new table"
```

### Apply Migrations

```bash
cd Traffic_Backend
alembic upgrade head
```

### Rollback Last Migration

```bash
cd Traffic_Backend
alembic downgrade -1
```

### View Database Schema

```bash
sqlite3 dev_navdrishti.db ".schema"
```

---

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'Traffic_Backend'`

**Solution:** Run commands from repo root and ensure `Traffic_Backend/__init__.py` exists.

```bash
cd c:\Users\abhis\HSC_NavDrishti_AHM
python -m pytest -q
```

### Issue: MySQL Connection Refused

**Solution:** Fallback to SQLite or provide correct DATABASE_URL.

```bash
# Check if MySQL is running
mysql -u root -p -e "SELECT 1;"

# If not, system will auto-fallback to SQLite
```

### Issue: "Access Denied" on Login

**Solution:** Verify admin user credentials.

```bash
# Reset admin user
python Traffic_Backend/init_db.py

# Re-run to reseed (admin / adminpass)
```

### Issue: Tests Fail with Import Errors

**Solution:** Ensure package structure is correct.

```bash
# Verify __init__.py exists
ls Traffic_Backend/__init__.py
ls Traffic_Backend/routers/__init__.py

# Run from repo root
cd c:\Users\abhis\HSC_NavDrishti_AHM
python -m pytest -q
```

---

## Next Steps

1. **Frontend Integration:** Connect ASP.NET dashboard to these backend endpoints
2. **Load Test Data:** Use Postman or curl to create sample projects and routes
3. **Upload GeoJSON:** Load road network for testing alternatives/recommendations
4. **Review API Docs:** Open `http://localhost:8000/docs` for interactive testing
5. **Check Progress:** See `IMPLEMENTATION_PROGRESS.md` for feature status

---

## Resources

- **Full API Reference:** `Traffic_Backend/API_REFERENCE.md`
- **SRS Document:** `SRS_SUMMARY.md`
- **Implementation Status:** `Traffic_Backend/IMPLEMENTATION_PROGRESS.md`
- **Test Files:** `Traffic_Backend/tests/`

---

**Need help?** Refer to the relevant markdown file or examine test examples in `Traffic_Backend/tests/`.

