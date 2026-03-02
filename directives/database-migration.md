# Directive: Database Migration

## Goal
Safely add or modify database schema using Alembic migrations.

## When to Create a Migration
- Adding a new table (new model)
- Adding/removing/renaming columns
- Changing column types or constraints
- Adding/removing indexes or foreign keys

## Steps

### 1. Modify Models
Edit the relevant `models.py` file using SQLAlchemy 2.0 syntax:
```python
class MyModel(TimestampMixin, Base):
    __tablename__ = "my_models"
    new_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

### 2. Generate Migration
```bash
cd backend
alembic revision --autogenerate -m "add new_field to my_models"
```

### 3. Review Generated Migration
Open the generated file in `backend/alembic/versions/` and verify:
- Correct table and column names
- Proper types and constraints
- `render_as_batch=True` is used (SQLite compatibility)

### 4. Apply Migration
```bash
# Local
cd backend && alembic upgrade head

# Production (via update.sh)
ssh user@vps '~/Accountant/update.sh'
```

## Critical Rules

### SQLite Compatibility
All migrations MUST use batch mode:
```python
def upgrade() -> None:
    with op.batch_alter_table("my_table") as batch_op:
        batch_op.add_column(sa.Column("new_field", sa.String(255), nullable=True))
```

### Database-Agnostic
- Never use SQLite-specific or PostgreSQL-specific SQL
- Always go through SQLAlchemy ORM
- Use `String(length)` instead of `Text` for indexed columns
- Use `uuid.uuid4` as default for primary keys

### Nullable New Columns
When adding columns to existing tables, make them `nullable=True` or provide a `server_default`:
```python
# Good: nullable
new_field: Mapped[str | None] = mapped_column(String(255), nullable=True)

# Good: server default
new_field: Mapped[str] = mapped_column(String(3), default="CAD", server_default="CAD")
```

## Rollback
```bash
# Revert last migration
cd backend && alembic downgrade -1

# Revert to specific revision
cd backend && alembic downgrade <revision_id>
```

## Security Requirements
- Migrations must not drop columns containing sensitive data without explicit approval
- Review all `DROP` and `ALTER` operations carefully
- Backup database before running destructive migrations in production

## Edge Cases
- **Migration conflicts**: If two branches add migrations, resolve by creating a merge revision
- **Data migration**: For data transforms, write a separate migration with `op.execute()` using parameterized queries
- **Large tables**: ALTER on large tables can lock the database — schedule during low-traffic periods

## Evaluation Criteria
- Migration applies cleanly: `alembic upgrade head` succeeds
- Migration reverts cleanly: `alembic downgrade -1` succeeds
- Both SQLite and PostgreSQL compatible
- No data loss
