from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User


ROLES = {"admin", "manager", "user", "viewer"}


def require_roles(*allowed_roles: str):
    def check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user role",
            )

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return check_role