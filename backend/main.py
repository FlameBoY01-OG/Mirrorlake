"""Mirrorlake backend — the single gateway between the frontends and the pipeline."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import dbt_runner, events, health, metrics, query
from services import kafka_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background Kafka consumer that feeds /events + the WebSocket stream.
    kafka_service.start_consumer()
    yield


app = FastAPI(title="Mirrorlake Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(events.router)
app.include_router(dbt_runner.router)
app.include_router(query.router)
app.include_router(metrics.router)


@app.get("/")
def root():
    return {"service": "mirrorlake-backend", "status": "ok"}
