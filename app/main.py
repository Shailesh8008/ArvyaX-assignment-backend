from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_database, initialize_database
from app.middleware.auth import UserNotFoundError, user_not_found_exception_handler
from app.settings import settings
from routers.journal import router as journal_router
from routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield
    close_database()


app = FastAPI(title="Journal Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(UserNotFoundError, user_not_found_exception_handler)
app.include_router(auth_router)
app.include_router(journal_router)


@app.get("/")
async def read_root():
    return {"service": "journal-service", "status": "ok"}


@app.get("/healthz")
async def healthcheck():
    return {"ok": True}
