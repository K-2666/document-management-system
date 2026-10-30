from typing import Literal

from pydantic import BaseModel


class UserRoleUpdate(BaseModel):
    role: Literal["admin", "manager", "user", "viewer"]