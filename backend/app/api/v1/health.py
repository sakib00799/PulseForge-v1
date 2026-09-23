from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Liveness endpoint: confirms that the API process can serve requests."""
    return {"status": "ok", "service": "pulseforge-api"}


@router.get("/health/ready")
def readiness_check() -> dict[str, str]:
    """Readiness endpoint: confirms that PostgreSQL is reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error

    return {"status": "ok", "database": "connected"}
