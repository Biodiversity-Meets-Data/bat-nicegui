"""Authentication API routes."""

from fastapi import APIRouter, HTTPException

from auth_utils import create_access_token, hash_password, verify_password
from database import create_user, get_user_by_email
from schemas import UserCreate, UserLogin

router = APIRouter()


@router.post("/api/auth/signup")
async def api_signup(user: UserCreate):
    existing = get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(user.password)
    user_id = create_user(user.email, hashed_pw, user.name)
    token = create_access_token(user_id)
    return {"access_token": token, "user_id": user_id}


@router.post("/api/auth/login")
async def api_login(user: UserLogin):
    db_user = get_user_by_email(user.email)
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(db_user["user_id"])
    return {"access_token": token, "user_id": db_user["user_id"]}
