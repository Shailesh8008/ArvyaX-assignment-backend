import json
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, status
from groq import GroqError

from app.db import get_journal_collection
from app.middleware.auth import require_user
from app.schemas import (
    JournalAnalysisResponse,
    JournalAnalyzeRequest,
    JournalCreate,
    JournalEntry,
)
from app.services.journal_analysis import analyze_emotion


router = APIRouter(prefix="/api/journal", tags=["journal"])


def _serialize_entry_document(entry: dict[str, Any], user_id: str) -> JournalEntry:
    entry_id = entry.get("id") or entry.get("_id") or ObjectId()
    created_at = entry.get("createdAt") or datetime.now(timezone.utc)

    return JournalEntry(
        id=str(entry_id),
        userId=user_id,
        ambience=entry["ambience"],
        text=entry["text"],
        createdAt=created_at,
    )


def _get_grouped_entries(journal_collection: Any, user_id: str) -> list[JournalEntry]:
    bucket = journal_collection.find_one(
        {"userId": user_id, "documentType": "journal_bucket"},
        {"entries": 1},
    )
    if not bucket:
        return []

    entries = bucket.get("entries", [])
    if not isinstance(entries, list):
        return []

    sorted_entries = sorted(
        [entry for entry in entries if isinstance(entry, dict)],
        key=lambda entry: entry.get("createdAt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return [_serialize_entry_document(entry, user_id) for entry in sorted_entries]


def _get_legacy_entries(journal_collection: Any, user_id: str) -> list[JournalEntry]:
    documents = journal_collection.find(
        {"userId": user_id, "documentType": {"$ne": "journal_bucket"}}
    ).sort("createdAt", -1)
    return [_serialize_entry_document(document, user_id) for document in documents]


@router.post("", response_model=JournalEntry, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    payload: JournalCreate,
    user_id: str = Depends(require_user),
) -> JournalEntry:
    if payload.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create journal entries for the logged-in user.",
        )

    journal_collection = get_journal_collection()
    entry = {
        "id": str(ObjectId()),
        "ambience": payload.ambience,
        "text": payload.text,
        "createdAt": datetime.now(timezone.utc),
    }
    journal_collection.update_one(
        {"userId": user_id, "documentType": "journal_bucket"},
        {
            "$setOnInsert": {
                "userId": user_id,
                "documentType": "journal_bucket",
            },
            "$push": {"entries": entry},
            "$set": {"updatedAt": entry["createdAt"]},
        },
        upsert=True,
    )

    return JournalEntry(
        id=entry["id"],
        userId=user_id,
        ambience=entry["ambience"],
        text=entry["text"],
        createdAt=entry["createdAt"],
    )


@router.post(
    "/analyze",
    response_model=JournalAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_journal(
    payload: JournalAnalyzeRequest,
    _: str = Depends(require_user),
) -> JournalAnalysisResponse:
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
def get_journal_entries(
    user_id: str,
    authenticated_user_id: str = Depends(require_user),
) -> list[JournalEntry]:
    if user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view journal entries for the logged-in user.",
        )

    journal_collection = get_journal_collection()
    grouped_entries = _get_grouped_entries(journal_collection, user_id)
    if grouped_entries:
        return grouped_entries

    return _get_legacy_entries(journal_collection, user_id)
