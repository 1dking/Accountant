
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.contacts.models import ActivityType, ContactType, FileSharePermission, InvitationStatus


class ContactCreate(BaseModel):
    type: ContactType
    company_name: str = Field(min_length=1, max_length=255)
    contact_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    zip_code: Optional[str] = Field(None, max_length=20)
    country: str = Field(default="US", max_length=100)
    tax_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    assigned_user_id: Optional[uuid.UUID] = None


class ContactUpdate(BaseModel):
    type: Optional[ContactType] = None
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    zip_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    assigned_user_id: Optional[uuid.UUID] = None


class ContactResponse(BaseModel):
    id: uuid.UUID
    type: ContactType
    company_name: str
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    country: str
    tax_id: Optional[str]
    notes: Optional[str]
    is_active: bool
    created_by: uuid.UUID
    assigned_user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactListItem(BaseModel):
    id: uuid.UUID
    type: ContactType
    company_name: str
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    city: Optional[str]
    state: Optional[str]
    is_active: bool
    assigned_user_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactFilter(BaseModel):
    search: Optional[str] = None
    type: Optional[ContactType] = None
    is_active: Optional[bool] = None
    tag: Optional[str] = None
    assigned_user_id: Optional[uuid.UUID] = None


# Tags
class TagRequest(BaseModel):
    tag_name: str = Field(min_length=1, max_length=100)


class BulkTagRequest(BaseModel):
    contact_ids: list[uuid.UUID]
    tag_name: str = Field(min_length=1, max_length=100)


class ContactTagResponse(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    tag_name: str
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# Activities
class ActivityCreate(BaseModel):
    activity_type: ActivityType
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[uuid.UUID] = None


class ContactActivityResponse(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    activity_type: ActivityType
    title: str
    description: Optional[str]
    reference_type: Optional[str]
    reference_id: Optional[uuid.UUID]
    created_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


# File shares
class FileShareCreate(BaseModel):
    file_id: uuid.UUID
    contact_id: uuid.UUID
    permission: FileSharePermission = FileSharePermission.VIEW


class FileShareResponse(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    contact_id: uuid.UUID
    permission: FileSharePermission
    shared_by: uuid.UUID
    shared_at: datetime

    model_config = {"from_attributes": True}


# Duplicate detection
class DuplicateGroup(BaseModel):
    field: str
    value: str
    contact_ids: list[uuid.UUID]


class MergeContactsRequest(BaseModel):
    primary_contact_id: uuid.UUID
    duplicate_contact_ids: list[uuid.UUID]


# Invitations
class InvitationCreate(BaseModel):
    email: str = Field(max_length=255)
    role: str = Field(max_length=50)
    contact_id: Optional[uuid.UUID] = None


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: InvitationStatus
    invited_by: uuid.UUID
    contact_id: Optional[uuid.UUID]
    expires_at: datetime
    accepted_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AcceptInvitationRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
