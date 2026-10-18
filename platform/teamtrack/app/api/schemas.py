"""Request and response models (house rule R3 conventions live in pagination.py and errors.py)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["admin", "member", "viewer"]
Status = Literal["open", "in_progress", "done"]
Priority = Literal["low", "medium", "high"]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrgOut(_Out):
    id: int
    name: str
    slug: str


class UserOut(_Out):
    id: int
    org_id: int
    email: str
    name: str
    role: Role


class ProjectOut(_Out):
    id: int
    org_id: int
    name: str
    key: str
    created_at: datetime


class MemberOut(_Out):
    project_id: int
    user_id: int
    added_at: datetime


class LabelBrief(_Out):
    id: int
    name: str
    color: str


class IssueOut(_Out):
    id: int
    org_id: int
    project_id: int
    title: str
    description: str
    status: Status
    priority: Priority
    assignee_id: int | None
    created_by: int
    version: int
    created_at: datetime
    updated_at: datetime
    labels: list[LabelBrief] = []


class AuditOut(_Out):
    id: int
    org_id: int
    actor_id: int
    action: str
    entity: str
    entity_id: int
    at: datetime


class LoginIn(_In):
    email: str = Field(min_length=3, max_length=200)


class LoginOut(BaseModel):
    token: str
    user: UserOut


class UserCreate(_In):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    name: str = Field(min_length=1, max_length=100)
    role: Role


class UserPatch(_In):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None


class ProjectCreate(_In):
    name: str = Field(min_length=1, max_length=100)
    key: str = Field(pattern=r"^[A-Z]{2,10}$")


class ProjectPatch(_In):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class MemberAdd(_In):
    user_id: int = Field(ge=1, le=2**63 - 1)


class IssueCreate(_In):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    priority: Priority = "medium"
    assignee_id: int | None = Field(default=None, ge=1, le=2**63 - 1)


class IssuePatch(_In):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    priority: Priority | None = None


class AssignIn(_In):
    assignee_id: int | None = Field(ge=1, le=2**63 - 1)


class TransitionIn(_In):
    status: Status


class HealthOut(BaseModel):
    status: str
