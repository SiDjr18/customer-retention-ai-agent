"""
Customer Retention AI Agent — FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import health, dataset, predict, agent, reports, recommend
from app.api.routes import scenario, multi_agent, upload

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade Customer Retention AI Agent API",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router,      tags=["Health"])
app.include_router(dataset.router,     prefix="/dataset",  tags=["Dataset"])
app.include_router(predict.router,     prefix="/predict",  tags=["Predict"])
app.include_router(agent.router,       prefix="/agent",    tags=["Agent"])
app.include_router(reports.router,     prefix="/reports",  tags=["Reports"])
app.include_router(recommend.router,   prefix="/recommend",tags=["Recommendations"])
app.include_router(scenario.router,    prefix="/scenario", tags=["Scenario Simulation"])
app.include_router(multi_agent.router, prefix="/agent",    tags=["Multi-Agent"])
app.include_router(upload.router,      prefix="/upload",   tags=["Upload"])
app.include_router(predict.router,     prefix="/model",    tags=["Model"], include_in_schema=True)


@app.on_event("startup")
async def on_startup() -> None:
    print(f"🚀  {settings.APP_NAME} v{settings.APP_VERSION} is starting up…")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    print("👋  Shutting down gracefully…")
