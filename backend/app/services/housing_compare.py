import re
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Profile, Housing, Budget


def amount(value):
    return str(value) if value is not None else None


def exact_total(values):
    return sum(values, Decimal('0.00')) if all(value is not None for value in values) else None


def context(db: Session, workspace_id: str):
    profile=db.scalar(select(Profile).where(Profile.workspace_id==workspace_id))
    budget=db.scalar(select(Budget).where(Budget.workspace_id==workspace_id))
    homes=list(db.scalars(select(Housing).where(Housing.workspace_id==workspace_id).order_by(Housing.name)))
    return profile,budget,homes


def calculate(db: Session, workspace_id: str, home_id: str | None = None):
    profile,budget,homes=context(db,workspace_id)
    home=next((h for h in homes if h.id==home_id),None) if home_id else None
    if home_id and home is None:
        raise ValueError('Housing option not found')
    fields=['rent','maintenance','utilities','food','transport','miscellaneous','deposit','moving_costs','setup_costs']
    values={key:getattr(budget,key) if budget else None for key in fields}
    if home:
        values['rent'],values['maintenance'],values['deposit']=home.rent,home.maintenance,home.deposit
    monthly=exact_total([values[key] for key in fields[:6]])
    upfront=exact_total([values[key] for key in fields[6:]])
    return {'home_id':home_id,'breakdown':{key:amount(value) for key,value in values.items()},
            'monthly_total':amount(monthly),'upfront_total':amount(upfront),
            'refundable_deposit':amount(values['deposit']),
            'monthly_limit':amount(profile.monthly_limit) if profile else None,
            'upfront_limit':amount(profile.upfront_limit) if profile else None,
            'monthly_affordable':monthly<=profile.monthly_limit if profile and monthly is not None and profile.monthly_limit is not None else None,
            'upfront_affordable':upfront<=profile.upfront_limit if profile and upfront is not None and profile.upfront_limit is not None else None}


STOP={'and','or','the','a','an','with','near','for','in','to','of','want','prefer','would','like','i','my'}


def compare(db: Session, workspace_id: str, home_ids: list[str] | None = None):
    profile,_,homes=context(db,workspace_id)
    if home_ids is not None:
        if any(home_id not in {home.id for home in homes} for home_id in home_ids):
            raise ValueError('Housing option not found')
        homes=[home for home in homes if home.id in home_ids]
    preference=(profile.housing_preferences or '') if profile else ''
    tokens=[token for token in re.findall(r'[a-z0-9]+',preference.lower()) if len(token)>2 and token not in STOP]
    commute_preference=(profile.commute_preferences or '') if profile else ''
    match=re.search(r'(?:under|within|maximum|max|up to)\s*(\d+)\s*(?:min|minute)',commute_preference.lower())
    commute_max=int(match.group(1)) if match else None
    results=[]
    for home in homes:
        calc=calculate(db,workspace_id,home.id)
        missing=[];strengths=[];tradeoffs=[];score=0;possible=0
        if calc['monthly_affordable'] is None: missing.append('Complete monthly costs and spending limit to check monthly affordability')
        else:
            possible+=40
            if calc['monthly_affordable']: score+=40;strengths.append('Within monthly limit using known inputs')
            else: tradeoffs.append('Exceeds monthly limit using known inputs')
        if calc['upfront_affordable'] is None: missing.append('Complete deposit, moving/setup costs, and upfront limit to check upfront affordability')
        else:
            possible+=25
            if calc['upfront_affordable']: score+=25;strengths.append('Within upfront limit using known inputs')
            else: tradeoffs.append('Exceeds upfront limit using known inputs')
        if home.commute_minutes is None: missing.append('User-entered commute time')
        if commute_max is None: missing.append('Commute time target for scoring')
        elif home.commute_minutes is not None:
            possible+=15
            if home.commute_minutes<=commute_max: score+=15;strengths.append('Meets your commute target')
            else: tradeoffs.append('Exceeds your commute target')
        if not tokens:
            missing.append('Specific housing preferences for scoring')
        else:
            possible+=20
            haystack=' '.join(filter(None,[home.name,home.locality,home.furnishing,home.notes])).lower()
            matched=[token for token in tokens if token in haystack]
            preference_score=round(20*len(matched)/len(tokens))
            score+=preference_score
            if matched: strengths.append('Matches preference terms: '+', '.join(matched))
            if len(matched)<len(tokens): tradeoffs.append('Unconfirmed preference terms: '+', '.join(token for token in tokens if token not in matched))
        results.append({'id':home.id,'name':home.name,'locality':home.locality,'source':home.source,
            'commute_minutes':home.commute_minutes,'costs':calc,'score':score,'score_possible':possible,
            'strengths':strengths,'tradeoffs':tradeoffs,'missing_information':missing})
    return sorted(results,key=lambda item:(-item['score'], -item['score_possible'], item['name']))
