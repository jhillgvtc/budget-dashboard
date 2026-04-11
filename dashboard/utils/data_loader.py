"""Load, unify, and filter bank + Chase CSV data."""

import glob
import os
import pathlib
from calendar import monthrange
from datetime import date

import pandas as pd
import streamlit as st
from utils.categorizer import categorize_bank_transaction

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"

# Google Sheets budget tracker (Atlas-maintained, published CSV)
BUDGET_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTNbwjd2qk42aLuGtMQb7GtDcIZ_T2XNXICn9nqyZWfmphhwXi2bBfMAKKy1ka9hrVz_n5CYT1OBDgI"
    "/pub?gid=1415714408&single=true&output=csv"
)

# Transaction types to exclude from expense analysis
NON_EXPENSE_TYPES = {"Income", "Transfer", "Investing"}

# Billing cycle config
CYCLE_START_DAY = 29
DEFAULT_BUDGET = 5_000

# Average cumulative spending % by day of billing cycle (computed from 8 cycles, Jul 2025 - Feb 2026).
# Day 1 = 29th of prior month, day 31 = 28th of cycle month.
# Update by re-running budgeting/analysis/checkpoint_billing_cycle.py with new CSVs.
DAILY_PACE_PCT = {
    1: 4.1, 2: 9.8, 3: 15.4, 4: 22.3, 5: 30.0,
    6: 33.9, 7: 37.7, 8: 41.2, 9: 44.2, 10: 47.0,
    11: 49.6, 12: 51.9, 13: 54.6, 14: 58.3, 15: 61.9,
    16: 65.0, 17: 67.0, 18: 69.2, 19: 71.1, 20: 73.6,
    21: 76.7, 22: 80.0, 23: 85.9, 24: 89.5, 25: 92.0,
    26: 92.9, 27: 95.0, 28: 96.5, 29: 97.8, 30: 98.9,
    31: 100.0,
}


@st.cache_data
def load_bank(path: pathlib.Path | None = None) -> pd.DataFrame:
    """Load and normalize bank checking CSV."""
    if path is None:
        # Set BANK_ACCOUNT_NUM env var or update this default for your account
        acct = os.environ.get("BANK_ACCOUNT_NUM", "ACCOUNT_NUM")
        path = DATA_DIR / f"20260209-{acct}.CSV"
    if not path.exists():
        return pd.DataFrame(columns=["date", "description", "amount", "category", "source", "type"])
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.strip('"')
    df["Post Date"] = df["Post Date"].str.strip('"')
    df["Amount"] = pd.to_numeric(df["Amount"].astype(str).str.strip('"'), errors="coerce")
    df["Payee"] = df["Payee"].astype(str).str.strip('"')

    out = pd.DataFrame({
        "date": pd.to_datetime(df["Post Date"], format="%m/%d/%Y"),
        "description": df["Payee"],
        "amount": df["Amount"],
        "category": df["Payee"].apply(categorize_bank_transaction),
        "source": "Bank",
        "type": df["Payee"].apply(_classify_bank_type),
    })
    return out


def _classify_bank_type(payee: str) -> str:
    """Classify a bank row as expense, income, transfer, or investing."""
    cat = categorize_bank_transaction(payee)
    if cat == "Income":
        return "Income"
    if cat == "Transfer":
        return "Transfer"
    if cat == "Investing":
        return "Investing"
    return "Expense"


@st.cache_data
def load_chase() -> pd.DataFrame:
    """Load all Chase CSVs from data/, deduplicate, return sales only."""
    # Set CHASE_CARD_SUFFIX env var or update this default for your card
    chase_suffix = os.environ.get("CHASE_CARD_SUFFIX", "Chase*")
    files = sorted(glob.glob(str(DATA_DIR / f"{chase_suffix}_Activity*.CSV")))
    if not files:
        return pd.DataFrame(columns=["date", "description", "amount", "category", "source", "type"])

    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)

    # Deduplicate on transaction date + description + amount
    df = df.drop_duplicates(
        subset=["Transaction Date", "Description", "Amount"],
        keep="first",
    )

    # Filter to Sale rows only (excludes Payment, Adjustment, Return)
    df = df[df["Type"].isin(["Sale"])].copy()

    out = pd.DataFrame({
        "date": pd.to_datetime(df["Transaction Date"], format="%m/%d/%Y"),
        "description": df["Description"],
        "amount": df["Amount"],
        "category": df["Category"],
        "source": "Chase",
        "type": "Expense",
    })
    return out


@st.cache_data
def load_chase_interest() -> pd.DataFrame:
    """Load interest/fee charges from all Chase CSVs for payoff analysis."""
    chase_suffix = os.environ.get("CHASE_CARD_SUFFIX", "Chase*")
    files = sorted(glob.glob(str(DATA_DIR / f"{chase_suffix}_Activity*.CSV")))
    if not files:
        return pd.DataFrame(columns=["date", "description", "amount"])

    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)

    # Deduplicate
    df = df.drop_duplicates(
        subset=["Transaction Date", "Description", "Amount"],
        keep="first",
    )

    # Filter to Fee rows with INTEREST in description
    mask = (df["Type"] == "Fee") & (df["Description"].str.contains("INTEREST", case=False, na=False))
    df = df[mask].copy()

    out = pd.DataFrame({
        "date": pd.to_datetime(df["Transaction Date"], format="%m/%d/%Y"),
        "description": df["Description"],
        "amount": df["Amount"],
    })
    return out


def _map_sheet_type(txn_type: str) -> str:
    """Map budget sheet Transaction Type to unified type."""
    txn_type = str(txn_type).strip().lower()
    if txn_type in ("payment", "credit"):
        return "Transfer"
    return "Expense"


@st.cache_data(ttl=300)
def load_budget_sheet() -> pd.DataFrame:
    """Fetch live Chase transactions from the Atlas-maintained Google Sheet."""
    try:
        df = pd.read_csv(BUDGET_SHEET_URL)
    except Exception:
        return pd.DataFrame(columns=["date", "description", "amount", "category", "source", "type"])

    # Drop empty rows (sheet has many blank trailing rows)
    df = df.dropna(subset=["Date", "Amount"])
    if df.empty:
        return pd.DataFrame(columns=["date", "description", "amount", "category", "source", "type"])

    out = pd.DataFrame({
        "date": pd.to_datetime(df["Date"], format="mixed"),
        "description": df["Summary"].astype(str),
        "amount": pd.to_numeric(df["Amount"], errors="coerce"),
        "category": df["Category Name"].fillna("Uncategorized"),
        "source": "Budget Sheet",
        "type": df["Transaction Type"].apply(_map_sheet_type),
    })
    return out


@st.cache_data
def load_all() -> pd.DataFrame:
    """Load and merge all sources into unified DataFrame."""
    bank = load_bank()
    chase = load_chase()
    sheet = load_budget_sheet()
    # Chase CSVs first (more complete history), then budget sheet fills in recent data
    combined = pd.concat([bank, chase, sheet], ignore_index=True)
    # Empty-frame branches in load_bank/load_chase produce object-dtype `date`,
    # which upcasts the whole column in concat and breaks downstream .dt access.
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    # Cross-source dedup: Chase CSVs and budget sheet track the same card
    combined = combined.drop_duplicates(
        subset=["date", "description", "amount"],
        keep="first",
    )
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


@st.cache_data
def load_expenses() -> pd.DataFrame:
    """Load only expense transactions (filtered from both sources)."""
    df = load_all()
    expenses = df[~df["type"].isin(NON_EXPENSE_TYPES)].copy()
    # Expenses are negative amounts -- make them positive for analysis
    expenses["amount_abs"] = expenses["amount"].abs()
    return expenses.reset_index(drop=True)


def get_date_range(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return min and max dates from a DataFrame."""
    return df["date"].min(), df["date"].max()


def filter_by_dates(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Filter DataFrame to date range (inclusive)."""
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df[mask].copy()


# ---------------------------------------------------------------------------
# Budget pacing
# ---------------------------------------------------------------------------

def get_billing_cycle_dates(ref_date: date | None = None) -> tuple[date, date]:
    """Return (cycle_start, cycle_end) for the billing cycle containing ref_date.

    Cycle runs from 29th of prior month through 28th of current month.
    If prior month has no 29th (Feb in non-leap years), starts on 1st of current month.
    """
    if ref_date is None:
        ref_date = date.today()

    if ref_date.day >= CYCLE_START_DAY:
        # In next month's cycle
        if ref_date.month == 12:
            cycle_month, cycle_year = 1, ref_date.year + 1
        else:
            cycle_month, cycle_year = ref_date.month + 1, ref_date.year
    else:
        cycle_month, cycle_year = ref_date.month, ref_date.year

    # Start = 29th of month before cycle_month
    if cycle_month == 1:
        prior_month, prior_year = 12, cycle_year - 1
    else:
        prior_month, prior_year = cycle_month - 1, cycle_year

    days_in_prior = monthrange(prior_year, prior_month)[1]
    if days_in_prior >= CYCLE_START_DAY:
        cycle_start = date(prior_year, prior_month, CYCLE_START_DAY)
    else:
        cycle_start = date(cycle_year, cycle_month, 1)

    cycle_end = date(cycle_year, cycle_month, 28)
    return cycle_start, cycle_end


def get_billing_cycle_pace_curve(budget: int = DEFAULT_BUDGET) -> dict[int, float]:
    """Return expected cumulative spend by day-of-cycle, scaled to budget.

    Uses the hardcoded DAILY_PACE_PCT derived from 8 months of Chase data.
    """
    return {day: pct / 100 * budget for day, pct in DAILY_PACE_PCT.items()}


def get_current_cycle_spend() -> tuple[float, date | None, int]:
    """Return (actual_spend, last_txn_date, day_of_cycle) for the current billing cycle.

    Uses budget sheet (live Finta data) first, falls back to load_expenses().
    """
    cycle_start, cycle_end = get_billing_cycle_dates()
    ts_start = pd.Timestamp(cycle_start)
    ts_end = pd.Timestamp(cycle_end)

    # Try budget sheet first (live data)
    sheet = load_budget_sheet()
    if not sheet.empty:
        mask = (
            (sheet["date"] >= ts_start)
            & (sheet["date"] <= ts_end)
            & (sheet["type"] == "Expense")
        )
        cycle_txns = sheet[mask]
    else:
        cycle_txns = pd.DataFrame()

    # Fall back to full expense data if sheet had nothing
    if cycle_txns.empty:
        expenses = load_expenses()
        mask = (expenses["date"] >= ts_start) & (expenses["date"] <= ts_end)
        cycle_txns = expenses[mask]

    if cycle_txns.empty:
        day_of_cycle = (date.today() - cycle_start).days + 1
        return 0.0, None, day_of_cycle

    actual_spend = cycle_txns["amount"].abs().sum()
    last_txn_date = cycle_txns["date"].max().date()
    day_of_cycle = (date.today() - cycle_start).days + 1
    return actual_spend, last_txn_date, day_of_cycle
