"""Joint tax filing — sprint 3 of the Canadian build.

One package per tax year: the business half (T2125 Statement of Business
Activities, mapped from the chart of accounts) and the personal half (T1
deductions/credits from the personal ledger), plus a readiness checklist.

Read-only across both ledgers. The business side reads the same postings the
P&L reads; the personal side reads PersonalTransaction. Nothing here writes to
either, and the personal half is only ever returned to its owner.
"""
