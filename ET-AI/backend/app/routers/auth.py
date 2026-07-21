from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import User, get_db
from ..envelope import ok
from ..security import (
    create_token,
    get_current_user,
    user_public,
    verify_password,
    verify_google_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str
    password: str


class GoogleLoginBody(BaseModel):
    id_token: str

@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email.lower().strip())).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return ok({
        "access_token": create_token(user),
        "token_type": "bearer",
        "user": user_public(user),
    })

from uuid import uuid4


@router.post("/google")
def google_login(body: GoogleLoginBody, db: Session = Depends(get_db)):
    google_user = verify_google_token(body.id_token)

    user = db.scalars(
        select(User).where(User.email == google_user["email"].lower())
    ).first()

    if user is None:
        user = User(
            user_id=str(uuid4()),
            name=google_user["name"],
            email=google_user["email"].lower(),
            password_hash="",
            role="Engineer",         
            plant_id="PLANT-01",      
            department="Maintenance",    
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    return ok({
        "access_token": create_token(user),
        "token_type": "bearer",
        "user": user_public(user),
    })


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok(user_public(user))
