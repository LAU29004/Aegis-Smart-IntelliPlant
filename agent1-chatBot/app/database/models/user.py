"""
app/database/models/user.py

WHY THIS FILE EXISTS
---------------------
The `User` model is the anchor for accountability across the rest of
the schema: which user uploaded a document, which user asked a query,
which user gave feedback on an answer. Kept intentionally minimal
(no password hashing scheme wired up yet, no auth flow) because the
spec does not define an authentication mechanism - this table exists
so that `user_id` foreign keys elsewhere in the schema have somewhere
valid to point to, and so a future auth layer has a ready-made table
to attach to without a migration that touches five other tables.
"""
from __future__ import annotations
from typing import Optional , List

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import UserRole


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A person who interacts with IntelliPlant - uploading documents,
    asking queries, or giving feedback on answers.

    WHY `hashed_password` is nullable: this service may sit behind an
    upstream SSO/identity provider (common in enterprise/industrial
    settings) where IntelliPlant never handles raw credentials at all,
    only a verified `username`/`email` passed through from that
    provider. Leaving it nullable supports both models without a
    schema change later.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, length=20),
        default=UserRole.VIEWER,
        nullable=False,
    )
    department: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Plant department this user belongs to, e.g. 'Maintenance', "
        "'Quality Assurance'. Used to default query filters and for "
        "analytics on which departments use the copilot most.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Relationships ---------------------------------------------
    # WHY `lazy="selectin"` is NOT used here (default lazy="select"
    # left in place): a User's uploaded documents / query logs can be
    # numerous. Eagerly loading them on every user fetch would be
    # wasteful for the common case (e.g. looking up a user just to
    # check their role). Callers that specifically need a user's
    # documents/history should query those tables directly, filtered
    # by user_id, rather than traversing this relationship in bulk.
    uploaded_documents: Mapped[List["Document"]] = relationship(  
        back_populates="uploaded_by_user",
        foreign_keys="Document.uploaded_by",
    )
    conversation_turns: Mapped[List["ConversationHistory"]] = relationship(  
        back_populates="user"
    )
    query_logs: Mapped[List["QueryLog"]] = relationship(  
        back_populates="user"
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship( 
        back_populates="user"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<User id={self.id} username={self.username!r} role={self.role.value}>"
