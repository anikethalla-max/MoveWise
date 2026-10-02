from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from app.core.config import settings

router=APIRouter(prefix='/auth',tags=['auth'])
oauth=OAuth()
if settings.auth_mode=='oidc':
    oauth.register('movewise',client_id=settings.oidc_client_id,client_secret=settings.oidc_client_secret,
        server_metadata_url=settings.oidc_metadata_url,
        client_kwargs={'scope':'openid profile','code_challenge_method':'S256'})


@router.get('/status')
def status(request:Request):
    if settings.auth_mode=='development':return {'mode':'development','authenticated':True,
        'mock_evaluation':settings.evaluation_mock_mode}
    identity=request.session.get('identity')
    return {'mode':'oidc','authenticated':bool(identity and identity.get('iss')==settings.oidc_issuer and identity.get('sub')),
        'mock_evaluation':False}


@router.get('/login')
async def login(request:Request):
    if settings.auth_mode!='oidc':raise HTTPException(404,'OIDC login is not configured')
    client=oauth.create_client('movewise')
    return await client.authorize_redirect(request,f'{settings.public_api_url}/auth/callback')


@router.get('/callback')
async def callback(request:Request):
    if settings.auth_mode!='oidc':raise HTTPException(404,'OIDC login is not configured')
    client=oauth.create_client('movewise')
    token=await client.authorize_access_token(request)
    userinfo=token.get('userinfo') or {}
    if not userinfo.get('sub') or userinfo.get('iss')!=settings.oidc_issuer:
        raise HTTPException(401,'OIDC identity validation failed')
    request.session.clear()
    request.session['identity']={'iss':userinfo['iss'],'sub':userinfo['sub']}
    return RedirectResponse(settings.frontend_url,status_code=303)


@router.get('/logout')
def logout(request:Request):
    if settings.auth_mode=='oidc':request.session.clear()
    return RedirectResponse(settings.frontend_url,status_code=303)
