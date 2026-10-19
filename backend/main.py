import re
from contextlib import asynccontextmanager
from typing import Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from auth.auth import authenticate_user, create_user, initialize_db, user_from_token
from services.assistant import answer_question
from services.gap_analyzer import analyze_product


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USER_TYPES = Literal["msme", "manufacturer", "consumer", "student"]
bearer_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app):
    initialize_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    language: str = "English"


class GapRequest(BaseModel):
    description: str
    language: str = "English"


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str
    password: str = Field(min_length=6)
    user_type: USER_TYPES


class LoginRequest(BaseModel):
    email: str
    password: str


def _user_for_credentials(credentials):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="A valid Bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return user_from_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="The session token is invalid or expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(request: RegisterRequest):
    if not EMAIL_PATTERN.fullmatch(request.email.strip()):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    try:
        user, token = create_user(request.name, request.email, request.password, request.user_type)
    except ValueError as error:
        message = str(error)
        status = 409 if "already exists" in message else 400
        raise HTTPException(status_code=status, detail=message) from None
    return {"token": token, "user": user}


@app.post("/auth/login")
def login(request: LoginRequest):
    authenticated = authenticate_user(request.email, request.password)
    if authenticated is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    user, token = authenticated
    return {"token": token, "user": user}


@app.get("/auth/me")
def auth_me(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    return {"user": _user_for_credentials(credentials)}


@app.post("/ask")
def ask(
    request: AskRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    user = _user_for_credentials(credentials) if credentials else None
    try:
        return answer_question(
            request.question,
            request.language,
            user["user_type"] if user else None,
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": "Assistant request failed."},
        )


@app.post("/gap")
def gap(
    request: GapRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    user = _user_for_credentials(credentials) if credentials else None
    try:
        result = analyze_product(
            request.description,
            request.language,
            user["user_type"] if user else None,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": "Specification gap analysis failed."},
        )
