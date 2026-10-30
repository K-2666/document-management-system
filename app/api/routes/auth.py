from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.audit_logging import log_audit
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    username = user_data.username.strip()
    email = str(user_data.email).strip().lower()

    existing_user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == username.lower(),
                func.lower(User.email) == email,
            )
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is already registered",
        )

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(user_data.password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is already registered",
        ) from None

    log_audit(
        action="USER_REGISTERED",
        user_id=user.id,
        details={"username": user.username},
    )

    return user


@router.post("/login", response_model=TokenResponse)
def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    username = credentials.username.strip()

    user = db.scalar(
        select(User).where(
            func.lower(User.username) == username.lower()
        )
    )

    if (
        user is None
        or not verify_password(credentials.password, user.hashed_password)
        or not user.is_active
    ):
        log_audit(
            action="LOGIN_FAILED",
            details={"username": username},
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.id)

    log_audit(
        action="LOGIN_SUCCESS",
        user_id=user.id,
        details={"username": user.username},
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user