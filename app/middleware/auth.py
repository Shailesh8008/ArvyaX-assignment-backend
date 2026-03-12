from bson import ObjectId
from fastapi import Request
from fastapi.responses import JSONResponse

from app.db import get_session_collection, get_user_collection


SESSION_COOKIE_NAME = "session_token"


class UserNotFoundError(Exception):
    pass


def require_user(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise UserNotFoundError()

    session_collection = get_session_collection()
    user_collection = get_user_collection()

    session = session_collection.find_one({"token": token})
    if session is None:
        raise UserNotFoundError()

    user = None
    user_id = session.get("userId")
    if isinstance(user_id, str):
        try:
            user = user_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            user = None

    if user is None:
        raise UserNotFoundError()

    request.state.user = {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
    }
    return str(user["_id"])


async def user_not_found_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"ok": False, "message": "user not exists"},
    )
