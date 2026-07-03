from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Header, HTTPException, status


Role = Literal["engineer", "admin", "viewer"]
VALID_ROLES: set[str] = {"engineer", "admin", "viewer"}
UNAUTHORIZED_MESSAGE = "You are not authorized to perform this action."


@dataclass(frozen=True)
class CurrentUser:
    name: str
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def get_current_user(
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> CurrentUser:
    name = (x_user_name or "engineer").strip() or "engineer"
    role = (x_user_role or "engineer").strip().lower()

    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNAUTHORIZED_MESSAGE,
        )

    return CurrentUser(name=name, role=role)  # type: ignore[arg-type]


def ensure_role(user: CurrentUser, allowed_roles: set[Role]) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNAUTHORIZED_MESSAGE,
        )
