from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.db import get_journal_collection, get_session_collection, get_user_collection
from app.middleware.auth import SESSION_COOKIE_NAME
from app.schemas import AuthSuccessResponse, AuthUserResponse, JournalEntry, UserLoginRequest, UserRegisterRequest
from app.settings import settings
from app.services.auth import create_session_token, hash_password, normalize_email, utc_now, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


def _journal_sort_key(entry: dict) -> datetime:
    created_at = entry.get("createdAt")
    if isinstance(created_at, datetime):
        return created_at

    return datetime.min.replace(tzinfo=timezone.utc)

def _serialize_user(document: dict) -> AuthUserResponse:
    return AuthUserResponse(
        id=str(document["_id"]),
        name=document["name"],
        email=document["email"],
        createdAt=document["createdAt"],
    )


def _serialize_journal(document: dict) -> JournalEntry:
    return JournalEntry(
        id=str(document.get("id") or document.get("_id")),
        userId=document["userId"],
        ambience=document["ambience"],
        text=document["text"],
        createdAt=document["createdAt"],
    )


def _get_user_journals(user_id: str) -> list[JournalEntry]:
    journal_collection = get_journal_collection()
    bucket = journal_collection.find_one(
        {"userId": user_id, "documentType": "journal_bucket"},
        {"entries": 1},
    )

    if bucket and isinstance(bucket.get("entries"), list):
        entries = sorted(
            [entry for entry in bucket["entries"] if isinstance(entry, dict)],
            key=_journal_sort_key,
            reverse=True,
        )
        return [
            _serialize_journal(
                {
                    "id": entry.get("id"),
                    "userId": user_id,
                    "ambience": entry["ambience"],
                    "text": entry["text"],
                    "createdAt": entry["createdAt"],
                }
            )
            for entry in entries
        ]

    legacy_documents = journal_collection.find(
        {"userId": user_id, "documentType": {"$ne": "journal_bucket"}}
    ).sort("createdAt", -1)
    return [_serialize_journal(document) for document in legacy_documents]


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        max_age=60 * 60 * 24 * 30,
    )


@router.post("/auth/register", response_model=AuthSuccessResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, response: Response) -> AuthSuccessResponse:
    user_collection = get_user_collection()
    session_collection = get_session_collection()
    email = normalize_email(payload.email)

    existing_user = user_collection.find_one({"email": email})
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists.")

    document = {
        "name": payload.name.strip(),
        "email": email,
        "passwordHash": hash_password(payload.password),
        "createdAt": utc_now(),
    }
    result = user_collection.insert_one(document)
    document["_id"] = result.inserted_id

    token = create_session_token()
    session_collection.insert_one(
        {
            "token": token,
            "userId": str(document["_id"]),
            "createdAt": utc_now(),
        }
    )
    _set_session_cookie(response, token)

    return AuthSuccessResponse(user=_serialize_user(document))


@router.post("/auth/login", response_model=AuthSuccessResponse, status_code=status.HTTP_200_OK)
def login(payload: UserLoginRequest, response: Response) -> AuthSuccessResponse:
    user_collection = get_user_collection()
    session_collection = get_session_collection()
    email = normalize_email(payload.email)

    user = user_collection.find_one({"email": email})
    if user is None or not verify_password(payload.password, user["passwordHash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    token = create_session_token()
    session_collection.insert_one(
        {
            "token": token,
            "userId": str(user["_id"]),
            "createdAt": utc_now(),
        }
    )
    _set_session_cookie(response, token)

    return AuthSuccessResponse(user=_serialize_user(user))


@router.post("/auth/logout", status_code=status.HTTP_200_OK)
def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        get_session_collection().delete_many({"token": token})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/user-details", status_code=status.HTTP_200_OK)
def get_user_details(request: Request) -> dict[str, object]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return {"ok": False, "message": "user does not exists"}

    session_collection = get_session_collection()
    user_collection = get_user_collection()
    session = session_collection.find_one({"token": token})
    if session is None or not isinstance(session.get("userId"), str):
        return {"ok": False, "message": "user does not exists"}

    try:
        user = user_collection.find_one({"_id": ObjectId(session["userId"])})
    except Exception:
        return {"ok": False, "message": "user does not exists"}

    if user is None:
        return {"ok": False, "message": "user does not exists"}

    return {
        "ok": True,
        "user": _serialize_user(user),
        "userId": str(user["_id"]),
        "journals": _get_user_journals(str(user["_id"])),
    }
