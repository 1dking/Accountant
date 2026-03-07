"""KYC Pydantic schemas."""

from pydantic import BaseModel, ConfigDict


class KycSubmitRequest(BaseModel):
    business_name: str | None = None
    business_type: str | None = None
    business_address: str | None = None
    business_phone: str | None = None
    business_website: str | None = None
    tax_id: str | None = None
    full_name: str | None = None
    date_of_birth: str | None = None
    personal_address: str | None = None
    government_id_type: str | None = None
    government_id_number: str | None = None


class KycResponse(BaseModel):
    id: str
    status: str
    business_name: str | None = None
    business_type: str | None = None
    business_phone: str | None = None
    full_name: str | None = None
    review_notes: str | None = None
    reviewed_at: str | None = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class KycReviewRequest(BaseModel):
    status: str  # "approved" or "rejected"
    review_notes: str | None = None
