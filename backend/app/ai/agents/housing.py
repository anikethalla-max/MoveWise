import json
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.ai.agents.runtime import run_agent
from app.ai.providers.llm import llm_provider
from app.services.housing_compare import context, calculate, compare, amount

SYSTEM = """You are MoveWise's Housing Agent. Use tools to inspect the server-owned workspace.
Choose tools based on the user's question and prior results. Never invent listings, availability, rents, or commute times.
Budget arithmetic, feasibility, and scoring come only from tools. A score is a transparent rule, not trained ML.
When profile or homes are missing and comparison is impossible, ask one targeted question.
Final output must be JSON: {"recommended_ids":[],"explanation":"...","targeted_question":null}.
Only recommend IDs returned by compare_housing_options. Explain missing inputs and tradeoffs.
"""

TOOLS=[
 {'type':'function','function':{'name':'get_relocation_profile','description':'Read the relocation profile','parameters':{'type':'object','properties':{},'additionalProperties':False}}},
 {'type':'function','function':{'name':'list_housing_options','description':'List saved housing options','parameters':{'type':'object','properties':{},'additionalProperties':False}}},
 {'type':'function','function':{'name':'calculate_budget','description':'Get deterministic budget numbers for a home or general budget','parameters':{'type':'object','properties':{'home_id':{'type':'string'}},'additionalProperties':False}}},
 {'type':'function','function':{'name':'compare_housing_options','description':'Compare saved homes with deterministic factors','parameters':{'type':'object','properties':{'home_ids':{'type':'array','items':{'type':'string'}}},'additionalProperties':False}}},
]


class HousingDecision(BaseModel):
    recommended_ids: list[str] = Field(default_factory=list)
    explanation: str
    targeted_question: str | None = None


def advise(db:Session,workspace_id:str,question:str,llm=None,limits=None,agent_run_id=None):
    if not question.strip(): raise ValueError('Question is required')
    compared={}
    def get_relocation_profile():
        profile,_,_=context(db,workspace_id)
        if not profile: return None
        return {'destination_city':profile.destination_city,'workplace_area':profile.workplace_area,
            'moving_date':profile.moving_date.isoformat() if profile.moving_date else None,
            'monthly_limit':amount(profile.monthly_limit),'upfront_limit':amount(profile.upfront_limit),
            'household_size':profile.household_size,'housing_preferences':profile.housing_preferences,
            'commute_preferences':profile.commute_preferences}
    def list_housing_options():
        _,_,homes=context(db,workspace_id)
        return [{'id':h.id,'name':h.name,'locality':h.locality,'rent':amount(h.rent),
            'maintenance':amount(h.maintenance),'deposit':amount(h.deposit),
            'commute_minutes':h.commute_minutes,'source':h.source} for h in homes]
    def calculate_budget(home_id=None): return calculate(db,workspace_id,home_id)
    def compare_housing_options(home_ids=None):
        items=compare(db,workspace_id,home_ids)
        compared.update({item['id']:item for item in items})
        return items
    content,activity=run_agent(llm or llm_provider(),SYSTEM,question,TOOLS,
        {'get_relocation_profile':get_relocation_profile,'list_housing_options':list_housing_options,
         'calculate_budget':calculate_budget,'compare_housing_options':compare_housing_options},
        limits=limits,agent_run_id=agent_run_id,agent_name='housing')
    decision=HousingDecision.model_validate(json.loads(content))
    if any(home_id not in compared for home_id in decision.recommended_ids):
        raise ValueError('Agent recommended a home without comparing it')
    profile,_,homes=context(db,workspace_id)
    targeted=decision.targeted_question
    if not homes: targeted='Which saved housing option would you like to compare? Add a home first.'
    elif not profile: targeted='What is your destination and monthly and upfront spending limits?'
    elif profile.monthly_limit is None or profile.upfront_limit is None:
        targeted=targeted or 'What are your monthly and upfront spending limits?'
    if not decision.recommended_ids and not targeted and not compared:
        raise ValueError('Agent must ask for missing information')
    return {'explanation':decision.explanation,'targeted_question':targeted,
        'recommendations':[compared[home_id] for home_id in decision.recommended_ids],
        'comparison':list(compared.values()),'activity':activity,
        'scoring':{'monthly_affordability':40,'upfront_affordability':25,'commute_target':15,'preference_terms':20}}
