import json
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.models import Workspace, Profile, Housing, Budget
from app.services.housing_compare import calculate, compare
from app.services.plans import PlanCandidate, create_proposal, current, confirm, cancel, set_completion, plan_view, StaleProposal
from app.ai.agents.housing import advise
from app.ai.agents.planning import propose


def db_fixture():
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    w=Workspace();other=Workspace();db.add_all([w,other]);db.commit()
    db.add(Profile(workspace_id=w.id,destination_city='Bengaluru',workplace_area='MG Road',moving_date=date(2027,1,15),
        monthly_limit=Decimal('50000'),upfront_limit=Decimal('100000'),household_size=2,
        housing_preferences='furnished Indiranagar',commute_preferences='under 30 minutes'))
    db.add(Budget(workspace_id=w.id,utilities=Decimal('2000'),food=Decimal('8000'),transport=Decimal('3000'),
        miscellaneous=Decimal('2000'),moving_costs=Decimal('5000'),setup_costs=Decimal('3000')))
    a=Housing(workspace_id=w.id,name='Home A',locality='Indiranagar',rent=Decimal('30000'),maintenance=Decimal('2000'),
        deposit=Decimal('80000'),furnishing='furnished',commute_minutes=25,source='user-entered')
    b=Housing(workspace_id=w.id,name='Home B',locality='Whitefield',rent=Decimal('42000'),maintenance=Decimal('3000'),
        deposit=Decimal('110000'),furnishing='unfurnished',commute_minutes=None,source='user-entered')
    db.add_all([a,b]);db.commit()
    return db,w,other,a,b


class HousingLLM:
    def __init__(self):self.calls=0
    def next(self,messages,tools):
        self.calls+=1
        if self.calls==1:return call('p','get_relocation_profile',{})
        if self.calls==2:return call('h','list_housing_options',{})
        if self.calls==3:return call('c','compare_housing_options',{})
        options=json.loads(messages[-1]['content'])
        return {'content':json.dumps({'recommended_ids':[options[0]['id']],
            'explanation':'This saved home fits the known budget and preferences.',
            'targeted_question':None})}


class PlanningLLM:
    def __init__(self,revision=False):self.calls=0;self.revision=revision
    def next(self,messages,tools):
        self.calls+=1
        if self.calls==1:return call('p','get_relocation_profile',{})
        if self.calls==2:return call('c','get_current_plan',{})
        if self.calls==3:return call('b','calculate_budget',{})
        if self.calls==4:
            previous=json.loads(messages[-2]['content']) if self.revision else None
            tasks=[{'id':previous['tasks'][0]['id'] if previous else None,'title':'Book movers','stage':'before-moving',
                'due_date':'2027-01-10','priority':'high','category':'Logistics','source_kind':'general','citation_chunk_ids':[]}]
            if self.revision:tasks.append({'id':None,'title':'Update address','stage':'after-moving','due_date':'2027-01-20',
                'priority':'medium','category':'Admin','source_kind':'general','citation_chunk_ids':[]})
            return call('new','propose_plan_changes',{'summary':'A plan for the Bengaluru move.','tasks':tasks,
                'assumptions':[],'missing_information':[]})
        result=json.loads(messages[-1]['content'])
        return {'content':json.dumps({'proposal_id':result['proposal_id'],'explanation':'Review this plan.',
            'targeted_question':None})}


def call(cid,name,args):
    return {'content':None,'tool_calls':[{'id':cid,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}


def task(title='Book movers',task_id=None):
    return {'id':task_id,'title':title,'stage':'before-moving','due_date':'2027-01-10',
        'priority':'high','category':'Logistics','source_kind':'general','citation_chunk_ids':[]}


def test_housing_calculator_and_agent_tools():
    db,w,other,a,b=db_fixture()
    ca=calculate(db,w.id,a.id)
    assert ca['monthly_total']=='47000.00' and ca['upfront_total']=='88000.00'
    ranked=compare(db,w.id)
    assert ranked[0]['id']==a.id and ranked[0]['score']>ranked[1]['score']
    assert ranked[1]['commute_minutes'] is None and ranked[1]['missing_information']
    result=advise(db,w.id,'Which home fits?',llm=HousingLLM())
    assert [item['tool'] for item in result['activity']]==['get_relocation_profile','list_housing_options','compare_housing_options']
    assert result['recommendations'][0]['id']==a.id
    assert result['recommendations'][0]['costs']['monthly_total']=='47000.00'
    assert compare(db,other.id)==[]
    profile=db.query(Profile).filter_by(workspace_id=w.id).one();profile.monthly_limit=Decimal('40000');db.commit()
    assert compare(db,w.id)[0]['costs']['monthly_affordable'] is False


def test_proposal_cancel_stale_idempotence_and_completion():
    db,w,other,a,b=db_fixture()
    initial=create_proposal(db,w.id,PlanCandidate(summary='Move to Bengaluru.',tasks=[task()]),{})
    assert current(db,w.id) is None
    cancel(db,w.id,initial['id'])
    assert current(db,w.id) is None
    first=create_proposal(db,w.id,PlanCandidate(summary='Move to Bengaluru.',tasks=[task()]),{})
    stale=create_proposal(db,w.id,PlanCandidate(summary='Alternative plan.',tasks=[task('Call movers')]),{})
    plan=confirm(db,w.id,first['id'])
    assert plan.version==1 and confirm(db,w.id,first['id']).id==plan.id
    try:confirm(db,w.id,stale['id']);assert False
    except StaleProposal:pass
    task_id=plan.tasks[0]['id'];set_completion(db,w.id,task_id,True)
    revision=create_proposal(db,w.id,PlanCandidate(summary='Revised Bengaluru move.',tasks=[task(task_id=task_id),
        {'title':'Update address','stage':'after-moving','due_date':'2027-01-20','priority':'medium','category':'Admin'}]),{})
    assert len(revision['changes']['additions'])==1 and not revision['changes']['removals']
    revised=confirm(db,w.id,revision['id'])
    assert revised.version==2 and plan_view(db,revised)['tasks'][0]['completed'] is True
    try:confirm(db,other.id,revision['id']);assert False
    except ValueError:pass


def test_planning_agent_creates_preview_without_applying():
    db,w,other,a,b=db_fixture()
    response=propose(db,w.id,'Create my plan',llm=PlanningLLM())
    assert response['proposal']['status']=='pending'
    assert current(db,w.id) is None
    assert [item['tool'] for item in response['activity']]==['get_relocation_profile','get_current_plan','calculate_budget','propose_plan_changes']
    plan=confirm(db,w.id,response['proposal']['id'])
    assert plan.tasks[0]['due_date']=='2027-01-10'


def test_preference_score_and_document_citation_validation():
    db,w,other,a,b=db_fixture()
    first=compare(db,w.id)
    profile=db.query(Profile).filter_by(workspace_id=w.id).one()
    profile.housing_preferences='Whitefield';db.commit()
    changed=compare(db,w.id)
    assert next(x for x in changed if x['id']==b.id)['score']>next(x for x in first if x['id']==b.id)['score']
    sourced={'title':'Check agreement notice wording','stage':'before-moving','due_date':'2027-01-10',
        'priority':'medium','category':'Documents','source_kind':'document','citation_chunk_ids':['chunk-1']}
    try:create_proposal(db,w.id,PlanCandidate(summary='Prepare for the move.',tasks=[sourced]),{});assert False
    except ValueError as exc:assert 'not retrieved' in str(exc)
    evidence={'chunk-1':{'chunk_id':'chunk-1','document_id':'doc-1','document_name':'guide.md',
        'page':None,'section':'Notice','excerpt':'Give 30 days notice.','visibility':'private','score':None}}
    preview=create_proposal(db,w.id,PlanCandidate(summary='Prepare for the move.',tasks=[sourced]),evidence)
    assert preview['candidate']['citations'][0]['chunk_id']=='chunk-1'


def test_profile_change_makes_proposal_stale():
    db,w,other,a,b=db_fixture()
    preview=create_proposal(db,w.id,PlanCandidate(summary='Prepare for the move.',tasks=[task()]),{})
    profile=db.query(Profile).filter_by(workspace_id=w.id).one()
    profile.moving_date=date(2027,1,20);db.commit()
    try:confirm(db,w.id,preview['id']);assert False
    except StaleProposal as exc:assert 'changed' in str(exc)
    assert current(db,w.id) is None
