from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from routers import documents, dashboard, search, knowledge, integrity


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="EKOS API",
    description="Enterprise Knowledge Operating System — IR-first enterprise knowledge platform (Phase 1-2: ingestion + document access)",
    version="0.2.0",
    lifespan=lifespan,
)

# Dev CORS: wide open for local frontend dev server. Tighten before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
app.include_router(integrity.router, prefix="/integrity", tags=["integrity"])
