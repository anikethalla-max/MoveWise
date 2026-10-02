from fastapi import FastAPI, Request
from sqlalchemy import text as sql_text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings
from app.db.session import SessionLocal
from app.api.routes.v1 import router
from app.api.routes.documents import router as documents_router
from app.api.routes.agents_plans import router as agents_plans_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.auth import router as auth_router

app = FastAPI(title="MoveWise API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
if settings.auth_mode=='oidc':
    app.add_middleware(SessionMiddleware,secret_key=settings.session_secret,same_site='lax',
        https_only=settings.environment=='production',max_age=8*60*60)


@app.middleware('http')
async def origin_and_headers(request:Request,call_next):
    if settings.environment=='production' and request.method in {'POST','PUT','PATCH','DELETE'}:
        allowed={origin.strip() for origin in settings.cors_origins.split(',')}
        if request.headers.get('origin') not in allowed:
            return JSONResponse(status_code=403,content={'error':{'code':'origin_denied','message':'Request origin not allowed'}})
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder({"error": {"code": "validation_error", "details": exc.errors()}}))


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": str(exc.detail)}})


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get('/api/v1/ready')
def ready():
    try:
        with SessionLocal() as db:db.execute(sql_text('SELECT 1'))
    except SQLAlchemyError:
        return JSONResponse(status_code=503,content={'status':'not_ready'})
    return {'status':'ready'}


app.include_router(router)
app.include_router(documents_router)
app.include_router(agents_plans_router)
app.include_router(assistant_router)
app.include_router(auth_router)
