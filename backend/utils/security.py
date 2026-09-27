from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from utils.config import (JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
                          FIRST_ADMIN_EMAIL, FIRST_ADMIN_PASSWORD, FIRST_ADMIN_NAME)
from utils.database import get_users_collection, now_utc
from utils.logger import logger

# Tells Swagger UI (/docs) where to get a token for the "Authorize" button
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# --- Passwords ---

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --- JWT ---

def _secret() -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not set. Add it to your .env file.")
    return JWT_SECRET_KEY


def create_access_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])


# --- Dependencies used by protected routes ---

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Returns the logged-in user, or raises 401 if the token is missing, invalid or expired."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = ObjectId(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired",
                            headers={"WWW-Authenticate": "Bearer"})
    except (jwt.InvalidTokenError, KeyError, InvalidId):
        raise credentials_error

    user = get_users_collection().find_one({"_id": user_id})
    if user is None or not user.get("is_active", False):
        logger.warning("Token presented for a missing or inactive user")
        raise credentials_error
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


def seed_first_admin() -> None:
    """Creates the administrator from FIRST_ADMIN_* settings when that account does not exist yet."""
    if not FIRST_ADMIN_EMAIL or not FIRST_ADMIN_PASSWORD:
        return
    users = get_users_collection()
    if users.find_one({"email": FIRST_ADMIN_EMAIL}):
        return
    users.insert_one({
        "full_name": FIRST_ADMIN_NAME, "email": FIRST_ADMIN_EMAIL, "password_hash": hash_password(FIRST_ADMIN_PASSWORD),
        "role": "admin", "is_active": True, "created_at": now_utc(), "last_login": None,
    })
    logger.info("First administrator account created from FIRST_ADMIN_* settings")


def user_to_out(user: dict) -> dict:
    """Converts a MongoDB user document into the UserOut response shape."""
    return {
        "id": str(user["_id"]),
        "full_name": user["full_name"],
        "email": user["email"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
        "last_login": user.get("last_login"),
    }
