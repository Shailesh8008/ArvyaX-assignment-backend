from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import close_database, initialize_database
from routers.journal import router as journal_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield
    close_database()


app = FastAPI(title="Journal Service", lifespan=lifespan)
app.include_router(journal_router)


@app.get("/")
async def read_root():
    return {"service": "journal-service", "status": "ok"}
