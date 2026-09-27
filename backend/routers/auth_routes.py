from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from utils.config import ALLOW_REGISTRATION, DEFAULT_USER_ROLE, ACCESS_TOKEN_EXPIRE_MINUTES
from utils.database import get_users_collection
from utils.logger import logger
from utils.schemas import UserCreate, UserLogin, UserOut, TokenResponse
from utils.security import (hash_password, verify_password, create_access_token,
                            get_current_user, user_to_out)

# Create Router
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Same message for "no such user" and "wrong password", so the API does not reveal which emails exist
INVALID_LOGIN = "Incorrect email or password"


def _token_response(user: dict) -> dict:
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user_to_out(user),
    }


def _authenticate(email: str, password: str) -> dict:
    users = get_users_collection()
    user = users.find_one({"email": email.strip().lower()})
    if user is None or not verify_password(password, user["password_hash"]):
        logger.info("Failed login attempt")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_LOGIN)
    if not user.get("is_active", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled")

    now = datetime.now(timezone.utc)
    users.update_one({"_id": user["_id"]}, {"$set": {"last_login": now}})
    user["last_login"] = now
    logger.info(f"User logged in: {user['_id']}")
    return user


# --- Routes ---

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate):
    """Creates a new account and logs the user in (returns a JWT)."""
    if not ALLOW_REGISTRATION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account creation is disabled")

    users = get_users_collection()
    # The first account becomes the administrator; later accounts get the default role
    role = "admin" if users.count_documents({}, limit=1) == 0 else DEFAULT_USER_ROLE

    user = {
        "full_name": body.full_name,
        "email": body.email.strip().lower(),
        "password_hash": hash_password(body.password),
        "role": role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
    }
    try:
        result = users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user["_id"] = result.inserted_id
    logger.info(f"New account created: {user['_id']} (role: {role})")
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
    """Logs in with email + password (JSON) and returns a JWT. Used by the Angular dashboard."""
    return _token_response(_authenticate(body.email, body.password))


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
async def login_form(form: OAuth2PasswordRequestForm = Depends()):
    """Same as /login but with form fields — lets the 'Authorize' button in /docs work (username = email)."""
    return _token_response(_authenticate(form.username, form.password))


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    """Returns the logged-in user. Protected: requires 'Authorization: Bearer <token>'."""
    return user_to_out(user)
