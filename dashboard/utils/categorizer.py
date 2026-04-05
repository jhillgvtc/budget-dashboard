"""Bank transaction categorizer using regex pattern matching on payee field."""

import os
import re

# Ordered list of (pattern, category) -- first match wins
CATEGORY_RULES = [
    # Income
    (r"PAYROLL", "Income"),
    (r"Dividend", "Income"),
    (r"Freedom Card Cashback", "Income"),
    (r"AMERIFLEX", "Income"),

    # Transfers (excluded from expenses)
    (r"Transfer to", "Transfer"),
    (r"Internet Transfer", "Transfer"),
    (r"Round Up Transfer", "Transfer"),
    (r"CHASE CREDIT CRD", "Transfer"),
    (r"ONLINE BILL PAYMENT Chase", "Transfer"),
    (r"CAPITAL ONE.*CRCARDPMT", "Transfer"),
    # Set BANK_TRANSFER_REF env var if your transfer reference differs
    (os.environ.get("BANK_TRANSFER_REF", r"TRANSFER_REF"), "Transfer"),

    # Investing
    (r"FID BKG SVC", "Investing"),
    (r"EDWARD JONES", "Investing"),

    # Housing
    (r"Fifth Third.*Mortgage", "Housing"),
    (r"ONLINE BILL PAYMENT Fifth Third", "Housing"),
    (r"SECURITY STATE", "Housing"),

    # Taxes & Fees
    (r"COMAL COUNTY", "Taxes & Fees"),
    (r"GUADALUPE CO", "Taxes & Fees"),
    (r"TEXAS TPF", "Taxes & Fees"),
    (r"Texas One Fund", "Taxes & Fees"),
    (r"Non RBFCU ATM", "Taxes & Fees"),

    # Insurance
    (r"TX FARM BUREAU", "Insurance"),
    (r"TEXAS FARM BUREA", "Insurance"),

    # Student Loan
    (r"ADVS ED SERV.*STUDNTLOAN", "Student Loan"),

    # Debt Payment
    (r"BEST BUY.*AUTO PYMT", "Debt Payment"),
    (r"LOWES.*PAYMENT", "Debt Payment"),

    # Food & Drink
    (r"MAGNOLIA PANCAK", "Food & Drink"),
    (r"WHATABURGER", "Food & Drink"),

    # Groceries
    (r"H-?E-?B", "Groceries"),

    # Shopping
    (r"AMAZON", "Shopping"),
    (r"eBay", "Shopping"),
    (r"SP TURNTABLELAB", "Shopping"),
    (r"SP BRICKELLBRAN", "Shopping"),
    (r"SQ \*YARD SALE", "Shopping"),

    # Bills & Utilities
    (r"TMNA SUBSCRIPTI", "Bills & Utilities"),

    # Health & Wellness
    (r"PY \*DBA CLEAR S", "Health & Wellness"),

    # Personal
    (r"VENMO", "Personal"),
    (r"PAYPAL", "Personal"),
    (r"CASH APP", "Personal"),

    # Uncategorized checks
    (r"Over Counter Check", "Uncategorized"),
    (r"Check \d+", "Uncategorized"),
]

_compiled_rules = [(re.compile(pattern, re.IGNORECASE), cat) for pattern, cat in CATEGORY_RULES]


def categorize_bank_transaction(payee: str) -> str:
    """Return a category for a bank transaction based on payee string."""
    for pattern, category in _compiled_rules:
        if pattern.search(payee):
            return category
    return "Uncategorized"
