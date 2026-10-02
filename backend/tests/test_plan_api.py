from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.models import Workspace, Profile, Housing
from app.db.session import get_db
from app.main import app
from app.services.plans import PlanCandidate, create_proposal


def test_plan_routes_confirm_cancel_and_ownership():
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    def override():
        with Session() as db:yield db
    app.dependency_overrides[get_db]=override
    try:
        with TestClient(app) as a,TestClient(app) as b:
            a.post('/api/v1/session');b.post('/api/v1/session')
            workspace_id=a.cookies.get('movewise_session')
            with Session() as db:
                home=Housing(workspace_id=workspace_id,name='Test home',locality='Test locality',source='user-entered')
                db.add(home);db.commit();home_id=home.id
            assert a.put('/api/v1/selection/home',json={'home_id':home_id}).status_code==200
            assert b.put('/api/v1/selection/home',json={'home_id':home_id}).status_code==404
            with Session() as db:
                candidate=PlanCandidate(summary='Prepare for the move.',tasks=[{'title':'Book movers','stage':'before-moving',
                    'due_date':None,'priority':'high','category':'Logistics'}],missing_information=['Moving date'])
                proposal=create_proposal(db,workspace_id,candidate,{})
                cancelled=create_proposal(db,workspace_id,candidate,{})
            assert b.post(f"/api/v1/plans/proposals/{proposal['id']}/confirm").status_code==404
            assert a.post(f"/api/v1/plans/proposals/{cancelled['id']}/cancel").status_code==200
            assert a.get('/api/v1/plans/current').json() is None
            first=a.post(f"/api/v1/plans/proposals/{proposal['id']}/confirm")
            assert first.status_code==200 and first.json()['version']==1
            assert a.post(f"/api/v1/plans/proposals/{proposal['id']}/confirm").json()['id']==first.json()['id']
            task_id=first.json()['tasks'][0]['id']
            assert a.put(f'/api/v1/plans/tasks/{task_id}/completion',json={'completed':True}).status_code==200
            assert a.get('/api/v1/plans/current').json()['tasks'][0]['completed'] is True
            assert b.get('/api/v1/plans/current').json() is None
            assert b.put(f'/api/v1/plans/tasks/{task_id}/completion',json={'completed':True}).status_code==404
            assert a.post(f"/api/v1/plans/proposals/{cancelled['id']}/confirm").status_code==409
    finally:
        app.dependency_overrides.pop(get_db,None)
