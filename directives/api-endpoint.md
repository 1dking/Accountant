# Directive: New API Endpoint

## Goal
Create a new backend API module or endpoint following project conventions.

## Module Structure

Every backend module follows this pattern:

```
backend/app/{module}/
    __init__.py
    models.py     # SQLAlchemy models (Mapped[] syntax)
    schemas.py    # Pydantic v2 request/response schemas
    service.py    # Business logic (async functions)
    router.py     # FastAPI endpoints (thin — delegates to service)
```

## Steps

### 1. Models (`models.py`)
```python
import uuid
import enum
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, TimestampMixin

class MyModel(TimestampMixin, Base):
    __tablename__ = "my_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ... fields
```

### 2. Schemas (`schemas.py`)
```python
import uuid
from pydantic import BaseModel, ConfigDict

class MyModelCreate(BaseModel):
    name: str

class MyModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
```

### 3. Service (`service.py`)
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.exceptions import NotFoundError

async def create_item(db: AsyncSession, data: MyModelCreate, user: User) -> MyModel:
    item = MyModel(**data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
```

### 4. Router (`router.py`)
```python
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()

@router.post("", status_code=201)
async def create_item(
    data: MyModelCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    item = await service.create_item(db, data, current_user)
    return {"data": MyModelResponse.model_validate(item)}
```

### 5. Register Router (`main.py`)
```python
from app.{module}.router import router as {module}_router
app.include_router({module}_router, prefix="/api/{module}", tags=["{module}"])
```

### 6. Database Migration
```bash
cd backend && alembic revision --autogenerate -m "add {module} table"
cd backend && alembic upgrade head
```

### 7. Frontend API Client
```typescript
// frontend/src/api/{module}.ts
import { api } from './client'
import type { ApiResponse } from '@/types/api'

export function getItems() {
  return api.get<ApiResponse<Item[]>>('/{module}')
}
```

## API Response Format

```json
// Success
{ "data": { ... }, "meta": { "total": 100, "page": 1 } }

// Error
{ "error": { "code": "NOT_FOUND", "message": "Resource not found" } }
```

## Security Requirements
- All endpoints require `get_current_user` unless explicitly public
- Write operations require `require_role([Role.ACCOUNTANT, Role.ADMIN])`
- Delete operations require `require_role([Role.ADMIN])`
- Never put business logic in routers

## Testing Requirements
- Happy path test (correct input → expected output)
- Auth test (no token → 401)
- Role test (wrong role → 403)
- Validation test (bad input → 422)

## Evaluation Criteria
- Endpoint responds correctly
- Auth/role restrictions enforced
- Response follows envelope format
- Database records created/updated correctly
- No N+1 query issues (use `selectinload`)
