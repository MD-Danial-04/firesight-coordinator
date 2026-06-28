import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.analyze import router as analyze_router
from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router
from app.routes.location import router as location_router
from app.routes.worker import router as worker_router

logger = logging.getLogger(__name__)

app = FastAPI(title="FireSight Coordinator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(analyze_router)
app.include_router(location_router)
app.include_router(worker_router)
