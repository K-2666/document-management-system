
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit_logging import log_audit
from app.db.session import get_db
from app.dependencies.permissions import require_roles
from app.models.user import User
from app.schemas.admin import UserRoleUpdate
from app.schemas.user import UserResponse


router = APIRouter(prefix="/admin", tags=["Administration"])


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )

    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    previous_role = user.role
    new_role = role_data.role

    user.role = new_role
    db.commit()
    db.refresh(user)

    log_audit(
        action="USER_ROLE_UPDATED",
        user_id=current_user.id,
        target_id=user.id,
        details={
            "previous_role": previous_role,
            "new_role": new_role,
        },
    )

    return user
