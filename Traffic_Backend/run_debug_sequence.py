import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Traffic_Backend.main import app
from Traffic_Backend.db_config import engine, SessionLocal
from Traffic_Backend.models import Base
from fastapi.testclient import TestClient

client = TestClient(app)

# reset DB
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

# register user
resp = client.post('/register', json={'username':'testuser','password':'testpass123','email':'test@example.com'})
print('/register', resp.status_code, resp.json())
# token
resp = client.post('/token', data={'username':'testuser','password':'testpass123'})
print('/token', resp.status_code, resp.json())
token = resp.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}
# create admin directly
db = SessionLocal()
from Traffic_Backend.auth import create_user
admin = create_user(db, 'admin_test', 'adminpass123', email='a@b.com', roles='admin')
db.close()
# admin token
resp = client.post('/token', data={'username':'admin_test','password':'adminpass123'})
print('/token(admin)', resp.status_code, resp.json())
admin_token = resp.json().get('access_token')
headers = {'Authorization': f'Bearer {admin_token}'}
# create project
resp = client.post('/projects/', json={'name':'Admin Project','status':'active'}, headers=headers)
print('create project', resp.status_code, resp.json())
proj = resp.json()
proj_id = proj['id']
# update project
resp = client.put(f'/projects/{proj_id}', json={'status':'completed'}, headers=headers)
print('update project', resp.status_code)
try:
    print(resp.json())
except Exception as e:
    print('no json body')
