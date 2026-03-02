# Input Validation Patterns

Validation rules and patterns used across the Accountant platform.

## Pydantic Validation (Backend)

All API inputs are validated via Pydantic v2 schemas before reaching service logic.

```python
# Example: Invoice creation schema
class InvoiceCreate(BaseModel):
    contact_id: uuid.UUID                    # Must be valid UUID
    issue_date: date                         # Must be valid date
    due_date: date                           # Must be valid date
    currency: str = "CAD"                    # Defaults to CAD
    line_items: list[LineItemCreate]          # At least one item
    tax_rate: float | None = None            # Optional
    notes: str | None = None                 # Optional, max 10000 chars
```

## File Upload Validation

Located in router endpoints that accept `UploadFile`:

```python
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "gif", "webp", "xlsx", "csv", "doc", "docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Pattern:
extension = filename.rsplit(".", 1)[-1].lower()
if extension not in ALLOWED_EXTENSIONS:
    raise ValidationError("File type not allowed")
```

## SQL Injection Prevention

- All database queries use SQLAlchemy ORM (never raw SQL)
- Parameters are always bound, never interpolated
- `select()`, `where()`, `filter()` handle escaping automatically

```python
# CORRECT: parameterized query
result = await db.execute(
    select(Invoice).where(Invoice.id == invoice_id)
)

# NEVER DO: string interpolation
# result = await db.execute(text(f"SELECT * FROM invoices WHERE id = '{invoice_id}'"))
```

## XSS Prevention

- Frontend uses React (auto-escapes JSX output)
- Never use `dangerouslySetInnerHTML` unless content is sanitized
- API responses are JSON (not rendered HTML)
- PDF generation uses ReportLab (not HTML rendering)

## UUID Validation

All resource IDs are UUID type in path parameters:

```python
@router.get("/{invoice_id}")
async def get_invoice(invoice_id: uuid.UUID, ...):
    # FastAPI validates UUID format automatically
    # Invalid UUIDs return 422 Unprocessable Entity
```

## Email Validation

- `email-validator` library for format validation
- Used in Pydantic schemas via `EmailStr` type

## Date Validation

- All dates use Python `date` type in schemas
- Future/past validation done in service layer where needed
