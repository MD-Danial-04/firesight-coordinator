from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer = HTTPBearer(auto_error=False)


def _verify_token(expected: str, credentials: HTTPAuthorizationCredentials | None) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def verify_web_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    _verify_token(settings.web_api_key, credentials)


def verify_worker_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    _verify_token(settings.worker_api_key, credentials)
