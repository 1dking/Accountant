"""Native Canadian payroll: employees, runs, stubs.

Three new tables, no changes to existing ones. Tenant-scoped by
(user_id, org_id) like chart_accounts. SIN + home address columns are
Fernet-encrypted at the ORM layer (EncryptedString) — stored as TEXT here.

Revision ID: j8g9h0a1b2c3
Revises: i7f8a9b0c1d2
"""
import sqlalchemy as sa
from alembic import op

revision = "j8g9h0a1b2c3"
down_revision = "i7f8a9b0c1d2"
branch_labels = None
depends_on = None

_M = sa.Numeric(12, 2)


def _money(name: str, nullable: bool = False):
    return sa.Column(name, _M, nullable=nullable, server_default="0")


def upgrade() -> None:
    op.create_table(
        "payroll_employees",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("user_id", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", sa.CHAR(32), nullable=True, index=True),
        sa.Column("contact_id", sa.CHAR(32), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("sin", sa.Text(), nullable=True),               # encrypted
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("address_line1", sa.Text(), nullable=True),     # encrypted
        sa.Column("address_line2", sa.Text(), nullable=True),     # encrypted
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("province", sa.String(2), nullable=True),
        sa.Column("postal_code", sa.String(10), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("job_title", sa.String(150), nullable=True),
        sa.Column("province_of_employment", sa.String(2), nullable=False, server_default="ON"),
        sa.Column("pay_type", sa.String(10), nullable=False),
        sa.Column("pay_rate", _M, nullable=False),
        sa.Column("pay_frequency", sa.String(15), nullable=False),
        sa.Column("default_hours_per_period", sa.Numeric(7, 2), nullable=True),
        sa.Column("td1_federal_claim", _M, nullable=True),
        sa.Column("td1_provincial_claim", _M, nullable=True),
        sa.Column("additional_tax_per_period", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("cpp_exempt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ei_exempt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vacation_pay_pct", sa.Numeric(5, 2), nullable=False, server_default="4.00"),
        sa.Column("vacation_pay_each_period", sa.Boolean(), nullable=False, server_default=sa.true()),
        _money("vacation_accrued_balance"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payroll_employees_tenant", "payroll_employees", ["user_id", "org_id"])

    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("user_id", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", sa.CHAR(32), nullable=True, index=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("pay_date", sa.Date(), nullable=False),
        sa.Column("pay_frequency", sa.String(15), nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="draft"),
        _money("total_gross"), _money("total_vacation_pay"),
        _money("total_cpp_employee"), _money("total_cpp_employer"),
        _money("total_ei_employee"), _money("total_ei_employer"),
        _money("total_federal_tax"), _money("total_provincial_tax"),
        _money("total_other_deductions"), _money("total_net"), _money("total_remittance"),
        sa.Column("journal_entry_id", sa.CHAR(32), sa.ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payroll_runs_tenant_paydate", "payroll_runs", ["user_id", "org_id", "pay_date"])

    op.create_table(
        "payroll_stubs",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("run_id", sa.CHAR(32), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("employee_id", sa.CHAR(32), sa.ForeignKey("payroll_employees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("hours", sa.Numeric(7, 2), nullable=True),
        sa.Column("rate", _M, nullable=False),
        _money("regular_pay"), _money("overtime_pay"), _money("bonus"), _money("vacation_pay"),
        _money("other_earnings"), _money("gross"),
        _money("cpp_employee"), _money("cpp2_employee"), _money("ei_employee"), _money("qpip_employee"),
        _money("federal_tax"), _money("provincial_tax"), _money("other_deductions"), _money("net_pay"),
        _money("cpp_employer"), _money("cpp2_employer"), _money("ei_employer"), _money("qpip_employer"),
        _money("insurable_earnings"),
        sa.Column("insurable_hours", sa.Numeric(7, 2), nullable=False, server_default="0"),
        _money("pensionable_earnings"),
        _money("ytd_gross"), _money("ytd_cpp_employee"), _money("ytd_cpp2_employee"), _money("ytd_ei_employee"),
        _money("ytd_qpip_employee"), _money("ytd_federal_tax"), _money("ytd_provincial_tax"),
        _money("ytd_insurable_earnings"), _money("ytd_pensionable_earnings"), _money("ytd_net"),
        sa.Column("province_of_employment", sa.String(2), nullable=False),
        sa.Column("tables_version", sa.String(10), nullable=False),
        sa.Column("pdf_storage_path", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "employee_id", name="uq_payroll_stub_run_employee"),
    )


def downgrade() -> None:
    op.drop_table("payroll_stubs")
    op.drop_index("ix_payroll_runs_tenant_paydate", "payroll_runs")
    op.drop_table("payroll_runs")
    op.drop_index("ix_payroll_employees_tenant", "payroll_employees")
    op.drop_table("payroll_employees")
