from fastapi import APIRouter

from app.api.v1.api_keys import key_router as api_key_router
from app.api.v1.api_keys import service_router as service_api_key_router
from app.api.v1.auth import router as auth_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.events import router as events_router
from app.api.v1.health import router as health_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.members import router as members_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.services import router as services_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(audit_logs_router, tags=["audit logs"])
api_router.include_router(organizations_router, tags=["organizations"])
api_router.include_router(members_router, tags=["organization members"])
api_router.include_router(services_router, tags=["services"])
api_router.include_router(service_api_key_router, tags=["API keys"])
api_router.include_router(api_key_router, tags=["API keys"])
api_router.include_router(events_router, tags=["events"])
api_router.include_router(incidents_router, tags=["incidents"])
