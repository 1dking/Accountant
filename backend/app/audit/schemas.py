import json
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    result: str
    actor_id: uuid.UUID | None = None
    actor_email: str | None = None
    tenant_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    metadata: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("metadata", mode="before")
    @classmethod
    def _parse_metadata(cls, v):
        # Accept the stored JSON string (from ORM attr metadata_json) or a dict.
        if v is None or isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @classmethod
    def from_row(cls, row) -> "AuditLogResponse":
        return cls(
            id=row.id,
            action=row.action,
            result=row.result,
            actor_id=row.actor_id,
            actor_email=row.actor_email,
            tenant_id=row.tenant_id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            ip_address=row.ip_address,
            metadata=row.metadata_json,
            created_at=row.created_at,
        )
