"""Versioned deterministic evaluation; no real-provider claims or external requests."""
import argparse
import json
import statistics
import tempfile
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.db.base import Base
from app.db.models import Workspace, Profile, Housing, Budget
from app.ai.agents.document import answer_question
from app.ai.agents.housing import advise
from app.ai.agents.planning import propose
from app.ai.agents.coordinator import coordinate
from app.ai.agents.runtime import SharedLimits
from app.ai.providers.embedding import MockEmbeddings
from app.ai.providers.mock_evaluation import ScriptedEvaluationLLM
from app.rag.retrieval import search
from app.services.documents import save_upload, process_one
from app.services.housing_compare import calculate, compare
from app.services.plans import current, confirm, cancel
from app.services.assistant_runs import create_run

ROOT=Path(__file__).resolve().parents[2]
DATASET=ROOT/'data'/'demo'/'evaluation-v1.json'
FILES={'agreement':'synthetic-rental-agreement.txt',
       'addendum':'synthetic-conflicting-addendum.txt',
       'injection':'synthetic-injection-note.txt'}


class NoRetrievalLLM:
    def next(self,messages,tools):
        return {'content':json.dumps({'answer':'The documents do not establish the answer without retrieval.',
            'citation_chunk_ids':[],'missing_information':['No evidence retrieved.'],
            'conflicts':[],'outcome_status':'unsupported'})}


def score_answer(result,case):
    text=result['answer'].lower()
    return result['outcome_status']==case['expected_status'] and all(term.lower() in text for term in case['expected_answer_terms'])


def setup(db):
    workspace=Workspace();other=Workspace();db.add_all([workspace,other]);db.commit()
    db.add(Profile(workspace_id=workspace.id,destination_city='Bengaluru',moving_date=date(2027,1,15),
        monthly_limit=Decimal('50000'),upfront_limit=Decimal('100000'),household_size=1,
        housing_preferences='furnished Indiranagar',commute_preferences='under 30 minutes'))
    db.add(Budget(workspace_id=workspace.id,utilities=Decimal('2000'),food=Decimal('8000'),
        transport=Decimal('3000'),miscellaneous=Decimal('2000'),moving_costs=Decimal('5000'),
        setup_costs=Decimal('3000')))
    for name,locality,rent,maintenance,deposit,furnishing,commute in [
        ('Synthetic home A','Indiranagar','30000','2000','80000','furnished',25),
        ('Synthetic home B','Whitefield','42000','3000','110000','unfurnished',None),
        ('Synthetic home C','Koramangala','36000','3500','95000','semi-furnished',40)]:
        db.add(Housing(workspace_id=workspace.id,name=name,locality=locality,rent=Decimal(rent),
            maintenance=Decimal(maintenance),deposit=Decimal(deposit),furnishing=furnishing,
            commute_minutes=commute,source='synthetic demo',
            notes='Synthetic evaluation data; not a live listing.'))
    db.commit()
    documents={}
    for key,filename in FILES.items():
        document=save_upload(db,workspace.id,filename,(ROOT/'data'/'demo'/filename).read_bytes())
        process_one(db,MockEmbeddings())
        assert document.status=='ready',document.error
        documents[key]=document.id
    return workspace,other,documents


def evaluate():
    dataset=json.loads(DATASET.read_text(encoding='utf-8'))
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    with tempfile.TemporaryDirectory() as directory,Session() as db:
        previous=settings.private_upload_dir;settings.private_upload_dir=directory
        try:
            workspace,other,documents=setup(db)
            agreement=[]
            for case in dataset['agreement_cases']:
                selected=[documents[name] for name in case['documents']]
                started=time.perf_counter()
                hits=search(db,workspace.id,case['question'],selected,limit=10,provider=MockEmbeddings())
                rag=answer_question(db,workspace.id,case['question'],selected,
                    llm=ScriptedEvaluationLLM(),embedder=MockEmbeddings())
                rag_latency=round((time.perf_counter()-started)*1000,2)
                started=time.perf_counter()
                no_retrieval=answer_question(db,workspace.id,case['question'],selected,
                    llm=NoRetrievalLLM(),embedder=MockEmbeddings())
                no_latency=round((time.perf_counter()-started)*1000,2)
                hit_text=' '.join(hit['excerpt'].lower() for hit in hits)
                cited_text=' '.join(hit['excerpt'].lower() for hit in rag['citations'])
                agreement.append({'id':case['id'],'rag_correct':score_answer(rag,case),
                    'no_retrieval_correct':score_answer(no_retrieval,case),
                    'retrieval_hit':all(term.lower() in hit_text for term in case['expected_evidence']) if case['expected_evidence'] else None,
                    'citation_valid':all(c['chunk_id'] in {hit['chunk_id'] for hit in hits} for c in rag['citations']),
                    'citation_supported':all(term.lower() in cited_text for term in case['expected_evidence']) if case['expected_evidence'] else None,
                    'rag_latency_ms':rag_latency,'no_retrieval_latency_ms':no_latency,
                    'rag_status':rag['outcome_status'],'citation_count':len(rag['citations'])})
            homes=list(db.query(Housing).filter_by(workspace_id=workspace.id).order_by(Housing.name))
            calc=calculate(db,workspace.id,homes[0].id)
            ranking=compare(db,workspace.id)
            routing=[];tasks=[]
            for case in dataset['routing_cases']:
                root,_=create_run(db,workspace.id,case['request'],'route-'+case['id'])
                limits=SharedLimits(max_tokens=200000)
                start=time.perf_counter()
                result=coordinate(db,root,limits,llm_factory=lambda agent:ScriptedEvaluationLLM(),embedder=MockEmbeddings())
                routing.append({'id':case['id'],'expected':case['expected_agents'],
                    'actual':[entry['agent'] for entry in result['specialist_results']],
                    'correct':[entry['agent'] for entry in result['specialist_results']]==case['expected_agents'],
                    'latency_ms':round((time.perf_counter()-start)*1000,2),
                    'token_estimate':limits.token_estimate,'provider_tokens':None,
                    'estimated_cost_usd':None})
            for case in dataset['task_cases']:
                required=case['required_agents']
                start=time.perf_counter()
                primary=required[0]
                if primary=='housing':solo=advise(db,workspace.id,case['request'],llm=ScriptedEvaluationLLM())
                elif primary=='document':solo=answer_question(db,workspace.id,case['request'],llm=ScriptedEvaluationLLM(),embedder=MockEmbeddings())
                else:solo=propose(db,workspace.id,case['request'],llm=ScriptedEvaluationLLM(),embedder=MockEmbeddings())
                solo_latency=round((time.perf_counter()-start)*1000,2)
                root,_=create_run(db,workspace.id,case['request'],'task-'+case['id'])
                limits=SharedLimits(max_tokens=200000)
                start=time.perf_counter()
                multi=coordinate(db,root,limits,llm_factory=lambda agent:ScriptedEvaluationLLM(),embedder=MockEmbeddings())
                multi_latency=round((time.perf_counter()-start)*1000,2)
                actual=[entry['agent'] for entry in multi['specialist_results'] if entry['status']=='completed']
                tasks.append({'id':case['id'],'required':required,'single_agents':[primary],
                    'single_completed':set(required).issubset({primary}),
                    'multi_agents':actual,'multi_completed':set(required).issubset(set(actual)),
                    'single_latency_ms':solo_latency,'multi_latency_ms':multi_latency})
            # Exercise the persistent-change gate independently of AI text.
            proposed=propose(db,workspace.id,'Create a moving plan',llm=ScriptedEvaluationLLM(),embedder=MockEmbeddings())['proposal']
            cancel(db,workspace.id,proposed['id'])
            cancelled_unchanged=current(db,workspace.id) is None
            proposed=propose(db,workspace.id,'Create a moving plan',llm=ScriptedEvaluationLLM(),embedder=MockEmbeddings())['proposal']
            confirmed=confirm(db,workspace.id,proposed['id'])
            duplicate_same=confirm(db,workspace.id,proposed['id']).id==confirmed.id
            isolated=search(db,other.id,'deposit',provider=MockEmbeddings())==[]
            supported=[row for row in agreement if row['retrieval_hit'] is not None]
            metrics={'dataset_version':dataset['version'],'provider':'deterministic mock evaluation',
                'dataset_size':{'agreement_cases':len(agreement),'routing_cases':len(routing),
                    'task_cases':len(tasks),'homes':len(homes),'documents':len(documents)},
                'retrieval_hit_rate':sum(row['retrieval_hit'] for row in supported)/len(supported),
                'rag_answer_correctness':sum(row['rag_correct'] for row in agreement)/len(agreement),
                'no_retrieval_answer_correctness':sum(row['no_retrieval_correct'] for row in agreement)/len(agreement),
                'citation_validity':sum(row['citation_valid'] for row in supported)/len(supported),
                'citation_support':sum(row['citation_supported'] for row in supported)/len(supported),
                'routing_accuracy':sum(row['correct'] for row in routing)/len(routing),
                'single_agent_task_completion':sum(row['single_completed'] for row in tasks)/len(tasks),
                'multi_agent_task_completion':sum(row['multi_completed'] for row in tasks)/len(tasks),
                'budget_constraint_violations':sum(item['costs']['monthly_affordable'] is False or item['costs']['upfront_affordable'] is False for item in ranking[:1]),
                'budget_expected_match':calc['monthly_total']==dataset['budget_case']['home_monthly_total'] and calc['upfront_total']==dataset['budget_case']['home_upfront_total'],
                'cancel_preserved_plan':cancelled_unchanged,'duplicate_confirmation_idempotent':duplicate_same,
                'workspace_isolated':isolated,
                'median_rag_latency_ms':statistics.median(row['rag_latency_ms'] for row in agreement),
                'median_no_retrieval_latency_ms':statistics.median(row['no_retrieval_latency_ms'] for row in agreement),
                'provider_tokens':None,'estimated_cost_usd':None}
            return {'metrics':metrics,'agreement_cases':agreement,'routing_cases':routing,'task_cases':tasks}
        finally:settings.private_upload_dir=previous


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=evaluate()
    text=json.dumps(result,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf-8')
        print(f'Wrote {args.output}')
    else:print(text)
