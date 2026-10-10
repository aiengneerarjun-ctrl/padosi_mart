import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


def write_audit(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id: uuid.UUID | str,
    old: dict | None = None,
    new: dict | None = None,
    reason: str | None = None,
    request: Request | None = None,
) -> None:
    """Audit row session me jodta hai, COMMIT nahi karta. Caller wahi commit karta hai jisme asli badlav hai,
    taaki ya to dono save hon ya dono nahi (audit ke bina badlav kabhi nahi)."""
    db.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            old_value=old,
            new_value=new,
            reason=reason,
            request_id=getattr(request.state, "request_id", None) if request else None,
        )
    )