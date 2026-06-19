"""AI Financial Counselor -- Claude-powered chat with expense context."""

import os
import streamlit as st
from utils.data_loader import load_expenses, filter_by_dates

st.set_page_config(page_title="AI Counselor", page_icon="🤖", layout="wide")
st.title("AI Financial Counselor")

# -- Resolve API key from env (local run) or Streamlit secrets (cloud) --
def _get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    # st.secrets raises if no secrets file exists at all (e.g. local run) -- guard it.
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return None


api_key = _get_api_key()
if not api_key:
    st.error(
        "**ANTHROPIC_API_KEY not found.**\n\n"
        "**On Streamlit Cloud:** open *Manage app → Settings → Secrets* and add:\n"
        "```toml\n"
        'ANTHROPIC_API_KEY = "sk-ant-..."\n'
        "```\n"
        "**Running locally:** set it first, e.g. in PowerShell:\n"
        "```powershell\n"
        '$env:ANTHROPIC_API_KEY = "sk-ant-..."\n'
        "```"
    )
    st.stop()

import anthropic

# -- Load expense data for context --
expenses = load_expenses()
date_range = st.session_state.get("date_range")
if isinstance(date_range, tuple) and len(date_range) == 2:
    df = filter_by_dates(expenses, date_range[0], date_range[1])
else:
    df = expenses.copy()

# -- Build financial summary for system prompt --
def build_expense_summary(df):
    total = df["amount_abs"].sum()
    count = len(df)
    days = max((df["date"].max() - df["date"].min()).days, 1)
    daily_avg = total / days

    cat_summary = (
        df.groupby("category")["amount_abs"]
        .agg(["sum", "count"])
        .sort_values("sum", ascending=False)
    )
    cat_lines = []
    for cat, row in cat_summary.iterrows():
        cat_lines.append(f"  - {cat}: ${row['sum']:,.2f} ({int(row['count'])} txns)")

    top_merchants = (
        df.groupby("description")["amount_abs"]
        .sum()
        .nlargest(10)
    )
    merch_lines = [f"  - {desc}: ${amt:,.2f}" for desc, amt in top_merchants.items()]

    recent = df.sort_values("date", ascending=False).head(10)
    recent_lines = []
    for _, r in recent.iterrows():
        recent_lines.append(
            f"  - {r['date'].strftime('%m/%d')}: {r['description']} -- ${r['amount_abs']:,.2f} ({r['category']})"
        )

    date_range_str = f"{df['date'].min().strftime('%b %d')} -- {df['date'].max().strftime('%b %d, %Y')}"

    return f"""FINANCIAL DATA SUMMARY ({date_range_str})
Total Expenses: ${total:,.2f}
Transaction Count: {count}
Daily Average: ${daily_avg:,.2f}
Data Period: {days} days

SPENDING BY CATEGORY:
{chr(10).join(cat_lines)}

TOP MERCHANTS:
{chr(10).join(merch_lines)}

RECENT TRANSACTIONS:
{chr(10).join(recent_lines)}

SOURCES: Bank checking account + Chase credit card (shared family card)
"""


expense_context = build_expense_summary(df)

SYSTEM_PROMPT = f"""You are a friendly, practical financial counselor analyzing a user's personal spending data.
You have access to their recent transaction history summarized below. Use this data to answer questions,
identify patterns, suggest improvements, and provide actionable financial advice.

Be direct and specific -- reference actual numbers and categories from the data. Avoid generic advice.
If asked about something not in the data, say so clearly.

{expense_context}"""

# -- Chat interface --
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask about your spending..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call Claude
    client = anthropic.Anthropic(api_key=api_key)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
            )
            reply = response.content[0].text
            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
