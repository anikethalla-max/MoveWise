import os
os.environ['DATABASE_URL'] = 'sqlite+pysqlite:///:memory:'
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.session import get_db
from app.main import app

engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread':False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def db_override():
    with Session() as db:
        yield db


def test_workspace_isolation_and_persistence():
    app.dependency_overrides[get_db] = db_override
    a, b = TestClient(app), TestClient(app)
    item = a.post('/api/v1/housing', json={'name':'Home A','locality':'Indiranagar','rent':'20000.00'}).json()
    assert a.get('/api/v1/housing').json()[0]['id'] == item['id']
    assert b.get('/api/v1/housing').json() == []
    assert b.get('/api/v1/housing/'+item['id']).status_code == 404
    assert b.put('/api/v1/housing/'+item['id'], json={'name':'Changed','locality':'Other'}).status_code == 404
    assert b.delete('/api/v1/housing/'+item['id']).status_code == 404
    a.put('/api/v1/profile',json={'destination_city':'Bengaluru','household_size':2})
    assert a.get('/api/v1/profile').json()['destination_city'] == 'Bengaluru'
    assert b.get('/api/v1/profile').json() is None
    a.put('/api/v1/budget',json={'rent':'12000.00'})
    assert a.get('/api/v1/budget').json()['rent'] == '12000.00'
    assert b.get('/api/v1/budget').json()['rent'] is None
    a.close()
    b.close()
    app.dependency_overrides.pop(get_db, None)
