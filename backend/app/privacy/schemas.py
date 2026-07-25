from pydantic import BaseModel


class DeleteRequest(BaseModel):
    #: Must equal "DELETE" to guard against accidental erasure.
    confirm: str
    reason: str | None = None
