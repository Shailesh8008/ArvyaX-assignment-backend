import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from groq import GroqError

from app.db import get_journal_collection
from app.schemas import (
    JournalAnalysisResponse,
    JournalAnalyzeRequest,
    JournalCreate,
    JournalEntry,
)
from app.services.journal_analysis import analyze_emotion


router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.post("", response_model=JournalEntry, status_code=status.HTTP_201_CREATED)
def create_journal_entry(payload: JournalCreate) -> JournalEntry:
    journal_collection = get_journal_collection()
    document = {
        "userId": payload.user_id,
        "ambience": payload.ambience,
        "text": payload.text,
        "createdAt": datetime.now(timezone.utc),
    }
    result = journal_collection.insert_one(document)
    document["_id"] = result.inserted_id

    return JournalEntry(
        id=str(document["_id"]),
        userId=document["userId"],
        ambience=document["ambience"],
        text=document["text"],
        createdAt=document["createdAt"],
    )


@router.post(
    "/analyze",
    response_model=JournalAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_journal(payload: JournalAnalyzeRequest) -> JournalAnalysisResponse:
    try:
        return analyze_emotion(payload.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except (GroqError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to analyze journal text with Groq.",
        ) from exc


@router.get("/{user_id}", response_model=list[JournalEntry], status_code=status.HTTP_200_OK)
def get_journal_entries(user_id: str) -> list[JournalEntry]:
    journal_collection = get_journal_collection()
    documents = journal_collection.find({"userId": user_id}).sort("createdAt", -1)

    return [
        JournalEntry(
            id=str(document["_id"]),
            userId=document["userId"],
            ambience=document["ambience"],
            text=document["text"],
            createdAt=document["createdAt"],
        )
        for document in documents
    ]
