from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from utils.config import ALLOW_REGISTRATION, DEFAULT_USER_ROLE, ACCESS_TOKEN_EXPIRE_MINUTES
from utils.database import get_users_collection
from utils.logger import logger
from utils.schemas import (AdminUserCreate, PasswordChange, UserCreate, UserLogin, UserOut, UserUpdate,
                           TokenResponse)
from utils.security import (hash_password, verify_password, create_access_token,
                            get_current_user, require_admin, user_to_out)

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


@router.get("/settings")
async def auth_settings():
    """Public: tells the login page whether self-registration is open."""
    return {"allow_registration": ALLOW_REGISTRATION}


@router.post("/change-password", response_model=TokenResponse)
async def change_password(body: PasswordChange, user: dict = Depends(get_current_user)):
    """Changes the logged-in user's password. Other sessions are signed out; this one gets a new token."""
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The new password must be different from the current one")

    # Whole seconds, so the new token (issued in this same second) is still accepted
    changed_at = datetime.now(timezone.utc).replace(microsecond=0)
    get_users_collection().update_one({"_id": user["_id"]}, {"$set": {
        "password_hash": hash_password(body.new_password), "password_changed_at": changed_at}})
    user["password_changed_at"] = changed_at
    logger.info(f"Password changed: {user['_id']}")
    return _token_response(user)


# --- User management (administrators) ---

def _get_user(user_id: str) -> dict:
    try:
        user = get_users_collection().find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        user = None
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/users", response_model=list[UserOut])
async def list_users(admin: dict = Depends(require_admin)):
    return [user_to_out(u) for u in get_users_collection().find().sort("created_at", 1)]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: AdminUserCreate, admin: dict = Depends(require_admin)):
    """Administrators add team members (works even when self-registration is switched off)."""
    user = {
        "full_name": body.full_name,
        "email": body.email.strip().lower(),
        "password_hash": hash_password(body.password),
        "role": body.role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
    }
    try:
        user["_id"] = get_users_collection().insert_one(user).inserted_id
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    logger.info(f"Account {user['_id']} created by administrator {admin['_id']} (role: {body.role})")
    return user_to_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, body: UserUpdate, admin: dict = Depends(require_admin)):
    """Changes a user's role or disables / re-enables the account. Administrators cannot lock themselves out."""
    target = _get_user(user_id)
    changes = body.model_dump(exclude_none=True)
    if target["_id"] == admin["_id"] and (changes.get("is_active") is False or changes.get("role", "admin") != "admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot disable or demote your own account")
    if changes:
        get_users_collection().update_one({"_id": target["_id"]}, {"$set": changes})
        logger.info(f"Account {target['_id']} updated by administrator {admin['_id']}: {changes}")
    return user_to_out(_get_user(user_id))
