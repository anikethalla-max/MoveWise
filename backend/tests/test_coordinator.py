import json
import tempfile
import uuid
from fastapi.testclient import TestClient
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.db.base import Base
from app.db.models import Workspace, Profile, Housing, Budget, AgentRun, PlanProposal, RunEvent, AssistantMessage
from app.ai.agents.coordinator import coordinate
from app.ai.agents.runtime import SharedLimits, AgentLimitError, AgentCancelled, run_agent
from app.ai.providers.embedding import MockEmbeddings
from app.services.documents import save_upload, process_one
from app.services.assistant_runs import create_run
from app.services import assistant_runs
from app.api.routes import assistant as assistant_routes
from app.db.session import get_db
from app.main import app


def database():
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    w=Workspace();other=Workspace();db.add_all([w,other]);db.commit()
    db.add(Profile(workspace_id=w.id,destination_city='Bengaluru',moving_date=date(2027,1,15),
        monthly_limit=Decimal('50000'),upfront_limit=Decimal('100000'),household_size=1))
    db.add(Budget(workspace_id=w.id,utilities=Decimal('2000'),food=Decimal('6000'),transport=Decimal('2000'),
        miscellaneous=Decimal('1000'),moving_costs=Decimal('4000'),setup_costs=Decimal('2000')))
    db.add(Housing(workspace_id=w.id,name='Sample home',locality='Indiranagar',rent=Decimal('30000'),
        maintenance=Decimal('2000'),deposit=Decimal('80000'),source='user-entered'))
    db.commit()
    return db,w,other


def call(cid,name,args):
    return {'content':None,'tool_calls':[{'id':cid,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}


class CoordinatorLLM:
    def __init__(self,agents):self.agents=agents;self.step=0
    def next(self,messages,tools):
        self.step+=1
        if self.step<=len(self.agents):
            agent=self.agents[self.step-1]
            return call(str(self.step),f'delegate_to_{agent}_agent',{'task':{'housing':'Compare my saved homes',
                'document':'What does the agreement say about the deposit?',
                'planning':'Create a moving checklist using prior findings'}[agent]})
        citations=[]
        for message in messages:
            if message['role']=='tool':
                result=json.loads(message['content'])
                if result.get('agent')=='document' and result.get('result'):
                    citations.extend(c['chunk_id'] for c in result['result']['citations'])
        return {'content':json.dumps({'answer':'The specialist results are shown below.',
            'citation_chunk_ids':citations,'missing_information':[],'conflicts':[]})}


class HousingLLM:
    def __init__(self):self.step=0
    def next(self,messages,tools):
        assert not any(x['function']['name'].startswith('delegate_') for x in tools)
        self.step+=1
        if self.step==1:return call('compare','compare_housing_options',{})
        homes=json.loads(messages[-1]['content'])
        return {'content':json.dumps({'recommended_ids':[homes[0]['id']],
            'explanation':'Known costs are within the entered limits.','targeted_question':None})}


class DocumentLLM:
    def __init__(self,fail=False):self.step=0;self.fail=fail
    def next(self,messages,tools):
        assert not any(x['function']['name'].startswith('delegate_') for x in tools)
        if self.fail:raise RuntimeError('simulated provider failure')
        self.step+=1
        if self.step==1:return call('search','search_documents',{'query':'deposit'})
        hits=json.loads(messages[-1]['content'])
        return {'content':json.dumps({'answer':'The agreement states a refundable deposit of INR 80000.',
            'citation_chunk_ids':[hits[0]['chunk_id']],'missing_information':[],
            'conflicts':[],'outcome_status':'answered'})}


class PlanningLLM:
    def __init__(self):self.step=0
    def next(self,messages,tools):
        assert not any(x['function']['name'].startswith('delegate_') for x in tools)
        self.step+=1
        if self.step==1:
            prior=json.loads(messages[1]['content'])['prior_findings']
            assert prior and prior[0]['agent']=='housing'
            return call('profile','get_relocation_profile',{})
        if self.step==2:return call('proposal','propose_plan_changes',{'summary':'Prepare for the Bengaluru move.',
            'tasks':[{'id':None,'title':'Book movers','stage':'before-moving','due_date':'2027-01-10',
                'priority':'high','category':'Logistics','source_kind':'general','citation_chunk_ids':[]}],
            'assumptions':[],'missing_information':[]})
        proposed=json.loads(messages[-1]['content'])
        return {'content':json.dumps({'proposal_id':proposed['proposal_id'],'explanation':'Review the proposed plan.',
            'targeted_question':None})}


def factory(agents,document_failure=False):
    return lambda agent: {'coordinator':lambda:CoordinatorLLM(agents),'housing':HousingLLM,
        'document':lambda:DocumentLLM(document_failure),'planning':PlanningLLM}[agent]()


def run_case(agents,document_failure=False,limits=None):
    with tempfile.TemporaryDirectory() as directory:
        settings.private_upload_dir=directory
        db,w,other=database()
        if 'document' in agents:
            save_upload(db,w.id,'agreement.txt',b'The refundable deposit is INR 80000.')
            process_one(db,MockEmbeddings())
        root,_=create_run(db,w.id,'Help with my move','test-key')
        budget=limits or SharedLimits(max_tokens=200000)
        result=coordinate(db,root,budget,llm_factory=factory(agents,document_failure),embedder=MockEmbeddings())
        children=list(db.scalars(select(AgentRun).where(AgentRun.parent_run_id==root.id)))
        return result,children,db,root


def test_simple_routing_only_relevant_specialist():
    housing,children,_,_=run_case(['housing'])
    assert [x.agent for x in children]==['housing']
    assert housing['specialist_results'][0]['result']['recommendations']
    document,children,_,_=run_case(['document'])
    assert [x.agent for x in children]==['document']
    assert document['citations'] and document['citations'][0]['excerpt'].startswith('The refundable')


def test_combined_delegation_and_unapplied_plan():
    result,children,db,root=run_case(['housing','document','planning'])
    assert [x.agent for x in children]==['housing','document','planning']
    assert result['citations'] and result['status']=='completed'
    assert result['specialist_results'][2]['result']['proposal']['status']=='pending'
    assert db.scalar(select(PlanProposal).where(PlanProposal.workspace_id==root.workspace_id)) is not None


def test_partial_failure_and_shared_limit():
    result,children,_,_=run_case(['housing','document'],document_failure=True)
    assert result['status']=='partial' and [x.status for x in children]==['completed','failed']
    assert 'document' in result['missing_information'][-1]
    budget=SharedLimits(max_tool_steps=1,max_tokens=200000)
    try:run_case(['housing','document'],limits=budget);assert False
    except AgentLimitError:pass


def test_cancellation_stops_before_delegation():
    budget=SharedLimits(cancel_check=lambda:True,max_tokens=200000)
    try:run_case(['housing'],limits=budget);assert False
    except AgentCancelled:pass


def test_cancellation_stops_following_specialists():
    db,w,other=database()
    root,_=create_run(db,w.id,'Compare and inspect agreement','cancel-after-housing')
    holder={}
    budget=SharedLimits(cancel_check=lambda:holder['budget'].tool_steps>=3,max_tokens=200000)
    holder['budget']=budget
    try:coordinate(db,root,budget,llm_factory=factory(['housing','document']),embedder=MockEmbeddings());assert False
    except AgentCancelled:pass
    assert [child.agent for child in db.scalars(select(AgentRun).where(AgentRun.parent_run_id==root.id))]==['housing']


def test_persisted_run_history_idempotency_and_cancellation():
    db,w,other=database()
    Session=sessionmaker(bind=db.bind)
    root,created=create_run(db,w.id,'Compare my homes','request-1')
    duplicate,created_again=create_run(db,w.id,'Different text','request-1')
    assert created and not created_again and duplicate.id==root.id
    original=assistant_runs.SessionLocal
    assistant_runs.SessionLocal=Session
    try:
        assistant_runs.execute_run(root.id,llm_factory=factory(['housing']),
            limits_config={'max_tokens':200000})
        db.expire_all();stored=db.get(AgentRun,root.id)
        assert stored.status=='completed' and stored.result['specialist_results'][0]['agent']=='housing'
        assert db.query(AssistantMessage).filter_by(conversation_id=root.conversation_id).count()==2
        events=db.scalars(select(RunEvent).where(RunEvent.root_run_id==root.id)).all()
        assert any(event.tool_name=='delegate_to_housing_agent' for event in events)
        assert all('secret' not in event.summary.lower() for event in events)
        cancelled,_=create_run(db,w.id,'Compare again','request-2',root.conversation_id)
        cancelled.cancel_requested=True;db.commit()
        assistant_runs.execute_run(cancelled.id,llm_factory=factory(['housing']),
            limits_config={'max_tokens':200000})
        db.expire_all()
        assert db.get(AgentRun,cancelled.id).status=='cancelled'
        assert db.scalar(select(AgentRun).where(AgentRun.parent_run_id==cancelled.id)) is None
    finally:
        assistant_runs.SessionLocal=original


def test_assistant_routes_history_sse_and_isolation():
    db,w,other=database()
    Session=sessionmaker(bind=db.bind)
    def override():
        with Session() as session:yield session
    original_worker=assistant_routes.execute_run
    original_stream_db=assistant_routes.SessionLocal
    original_run_db=assistant_runs.SessionLocal
    app.dependency_overrides[get_db]=override
    assistant_routes.execute_run=lambda run_id:None
    assistant_routes.SessionLocal=Session
    assistant_runs.SessionLocal=Session
    try:
        with TestClient(app) as a,TestClient(app) as b:
            key=str(uuid.uuid4())
            first=a.post('/api/v1/assistant/messages',json={'content':'Compare homes','request_key':key})
            assert first.status_code==202 and first.json()['created'] is True
            repeated=a.post('/api/v1/assistant/messages',json={'content':'Compare homes','request_key':key})
            assert repeated.json()['created'] is False and repeated.json()['run_id']==first.json()['run_id']
            run_id=first.json()['run_id'];conversation_id=first.json()['conversation_id']
            assistant_runs.execute_run(run_id,llm_factory=factory(['housing']),limits_config={'max_tokens':200000})
            assert a.get(f'/api/v1/assistant/conversations/{conversation_id}').json()['messages'][-1]['role']=='assistant'
            assert b.get(f'/api/v1/assistant/conversations/{conversation_id}').status_code==404
            assert b.get(f'/api/v1/assistant/runs/{run_id}').status_code==404
            assert a.get(f'/api/v1/assistant/runs/{run_id}').json()['specialist_runs'][0]['agent']=='housing'
            stream=a.get(f'/api/v1/assistant/runs/{run_id}/events')
            assert stream.status_code==200 and 'event: activity' in stream.text and 'event: done' in stream.text
    finally:
        assistant_routes.execute_run=original_worker
        assistant_routes.SessionLocal=original_stream_db
        assistant_runs.SessionLocal=original_run_db
        app.dependency_overrides.pop(get_db,None)


def test_shared_time_token_limits_and_bounded_retry():
    class Flaky:
        def __init__(self):self.calls=0
        def next(self,messages,tools):
            self.calls+=1
            if self.calls==1:
                from httpx import TimeoutException
                raise TimeoutException('temporary')
            return {'content':'{"ok":true}'}
    flaky=Flaky()
    answer,_=run_agent(flaky,'system','question',[],{},limits=SharedLimits(max_tokens=1000))
    assert answer=='{"ok":true}' and flaky.calls==2
    try:run_agent(Flaky(),'system','question',[],{},limits=SharedLimits(max_tokens=1));assert False
    except AgentLimitError:pass
    try:SharedLimits(max_seconds=-1).check();assert False
    except AgentLimitError:pass
