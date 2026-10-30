from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging_config import logger
from app.core.exception_handlers import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.sharing import router as sharing_router
from app.api.routes.admin import router as admin_router
from app.core.rate_limiter import LoginRateLimitMiddleware


app = FastAPI(
    title="Document Management & Secure File Sharing System",
    version="1.0.0",
    description="API for document management, secure file sharing, and role-based access control.",
)

app.add_middleware(
    LoginRateLimitMiddleware,
    max_attempts=5,
    window_seconds=60,
)

app.add_exception_handler(
    StarletteHTTPException,
    http_exception_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

app.add_exception_handler(
    Exception,
    unhandled_exception_handler,
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(sharing_router)
app.include_router(admin_router)

logger.info("Document Management System API initialized")


@app.get("/")
def root():
    return {
        "message": "Document Management System API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }