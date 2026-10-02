"""Deterministic evaluation double. Never use or label as a real AI provider."""
import json
import re
from datetime import date, timedelta


def tool(cid,name,args):
    return {'content':None,'tool_calls':[{'id':cid,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}


class ScriptedEvaluationLLM:
    def __init__(self):
        self.step=0;self.profile=None;self.current=None;self.delegates=[]

    def next(self,messages,tools):
        system=messages[0]['content']
        if 'Relocation Coordinator' in system:return self.coordinator(messages)
        if 'Housing Agent' in system:return self.housing(messages)
        if 'Document Agent' in system:return self.document(messages)
        if 'Planning Agent' in system:return self.planning(messages)
        raise ValueError('Unknown evaluation agent')

    def coordinator(self,messages):
        request=json.loads(messages[1]['content'])['current_request'].lower()
        if self.step==0:
            if any(word in request for word in ['home','housing','compare','rent']):self.delegates.append('housing')
            if any(word in request for word in ['agreement','document','notice','deposit clause']):self.delegates.append('document')
            if any(word in request for word in ['plan','checklist','task','moving steps','update']):self.delegates.append('planning')
            if not self.delegates:self.delegates=['housing']
        if self.step<len(self.delegates):
            agent=self.delegates[self.step];self.step+=1
            return tool(str(self.step),f'delegate_to_{agent}_agent',{'task':request})
        citations=[];parts=[]
        for message in messages:
            if message['role']!='tool':continue
            result=json.loads(message['content'])
            if result.get('status')!='completed':continue
            agent=result.get('agent');value=result.get('result') or {}
            if agent=='housing':parts.append(value.get('explanation','Housing comparison available.'))
            if agent=='document':
                parts.append(value.get('answer','Document answer available.'))
                citations.extend(c['chunk_id'] for c in value.get('citations',[]))
            if agent=='planning':parts.append('A plan preview is ready for review; it has not been applied.')
        return {'content':json.dumps({'answer':' '.join(parts) or 'The requested information is unavailable.',
            'citation_chunk_ids':list(dict.fromkeys(citations)),'missing_information':[],'conflicts':[]})}

    def housing(self,messages):
        self.step+=1
        if self.step==1:return tool('compare','compare_housing_options',{})
        options=json.loads(messages[-1]['content'])
        if not options:
            return {'content':json.dumps({'recommended_ids':[],'explanation':'No saved homes to compare.',
                'targeted_question':'Which home would you like to add first?'})}
        return {'content':json.dumps({'recommended_ids':[options[0]['id']],
            'explanation':'The first saved home ranks highest on the known deterministic factors.',
            'targeted_question':None})}

    def document(self,messages):
        self.step+=1
        question=messages[1]['content'].lower()
        if self.step==1:return tool('search','search_documents',{'query':question,'limit':10})
        hits=json.loads(messages[-1]['content'])
        if 'notice' in question:
            sixty=[h for h in hits if '60 days' in h['excerpt']]
            thirty=[h for h in hits if '30-day' in h['excerpt'] or '30 days' in h['excerpt']]
            if sixty and thirty:
                return {'content':json.dumps({'answer':'The documents conflict: one says 60 days and another says 30 days of written notice.',
                    'citation_chunk_ids':[sixty[0]['chunk_id'],thirty[0]['chunk_id']],
                    'missing_information':['The documents do not establish which clause governs.'],
                    'conflicts':['60-day and 30-day notice clauses conflict.'],'outcome_status':'partial'})}
            if sixty:
                return {'content':json.dumps({'answer':'The agreement wording states 60 days of written notice.',
                    'citation_chunk_ids':[sixty[0]['chunk_id']],'missing_information':[],
                    'conflicts':[],'outcome_status':'answered'})}
        if 'deposit' in question:
            evidence=next((h for h in hits if '80,000' in h['excerpt'] and 'agreement' in h['document_name'].lower()),None)
            if evidence is None:evidence=next((h for h in hits if '80,000' in h['excerpt']),None)
            if evidence:
                return {'content':json.dumps({'answer':'The document wording states a refundable deposit of INR 80,000.',
                    'citation_chunk_ids':[evidence['chunk_id']],'missing_information':[],
                    'conflicts':[],'outcome_status':'answered'})}
        return {'content':json.dumps({'answer':'The documents do not establish the answer.',
            'citation_chunk_ids':[],'missing_information':['No supporting clause was found.'],
            'conflicts':[],'outcome_status':'unsupported'})}

    def planning(self,messages):
        self.step+=1
        if self.step==1:return tool('profile','get_relocation_profile',{})
        if self.step==2:
            self.profile=json.loads(messages[-1]['content'])
            return tool('current','get_current_plan',{})
        if self.step==3:
            self.current=json.loads(messages[-1]['content'])
            return tool('budget','calculate_budget',{})
        if self.step==4:
            if not self.profile or not self.profile.get('moving_date'):
                return {'content':json.dumps({'proposal_id':None,'explanation':'A move date is needed for due dates.',
                    'targeted_question':'What is your moving date?'})}
            moving=date.fromisoformat(self.profile['moving_date'])
            base=[('Book movers','before-moving',moving-timedelta(days=7),'Logistics'),
                  ('Confirm handover','moving-day',moving,'Housing'),
                  ('Update address','after-moving',moving+timedelta(days=7),'Admin')]
            prior={(t['stage'],t['title']):t['id'] for t in (self.current or {}).get('tasks',[])}
            tasks=[{'id':prior.get((stage,title)),'title':title,'stage':stage,'due_date':due.isoformat(),
                    'priority':'high' if stage!='after-moving' else 'medium','category':category,
                    'source_kind':'general','citation_chunk_ids':[]} for title,stage,due,category in base]
            if self.current:
                tasks.append({'id':prior.get(('before-moving','Review moving contacts')),
                    'title':'Review moving contacts','stage':'before-moving',
                    'due_date':(moving-timedelta(days=2)).isoformat(),'priority':'medium',
                    'category':'Logistics','source_kind':'general','citation_chunk_ids':[]})
            return tool('proposal','propose_plan_changes',{'summary':f"Moving plan for {self.profile['destination_city']}.",
                'tasks':tasks,'assumptions':[],'missing_information':[]})
        proposal=json.loads(messages[-1]['content'])
        return {'content':json.dumps({'proposal_id':proposal['proposal_id'],
            'explanation':'Review the proposed tasks and confirm if they fit your move.',
            'targeted_question':None})}
