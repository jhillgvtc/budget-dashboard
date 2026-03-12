"""Personal Budget AI -- Overview Page."""

from datetime import date

import streamlit as st
import plotly.express as px
from utils.data_loader import (
    load_expenses, get_date_range, filter_by_dates,
    get_billing_cycle_pace_curve, get_current_cycle_spend,
    get_billing_cycle_dates,
)
from utils.charts import get_color_sequence, PLOTLY_LAYOUT

st.set_page_config(
    page_title="Personal Budget AI",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -- Sidebar: date filter (persists across pages via session_state) --
expenses = load_expenses()
date_min, date_max = get_date_range(expenses)
cycle_start, _cycle_end = get_billing_cycle_dates()

st.sidebar.title("Filters")
date_range = st.sidebar.date_input(
    "Date range",
    value=(cycle_start, date.today()),
    min_value=date_min.date(),
    max_value=date.today(),
    key="date_range",
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
else:
    start, end = cycle_start, date.today()

df = filter_by_dates(expenses, start, end)

# -- Header --
st.title("Personal Budget AI")
st.caption(f"{start.strftime('%b %d')} -- {end.strftime('%b %d, %Y')}  |  {len(df)} transactions")

# -- Budget Pace (always shows current billing cycle, ignores sidebar filter) --
pace_curve = get_billing_cycle_pace_curve()
actual_spend, last_txn_date, day_of_cycle = get_current_cycle_spend()
expected = pace_curve.get(day_of_cycle, 5000)
variance = expected - actual_spend  # positive = under pace (good)

st.subheader("Budget Pace")
p1, p2, p3, p4 = st.columns(4)
p1.metric("Day of Cycle", f"{day_of_cycle} of ~30")
p2.metric("Actual Spend", f"${actual_spend:,.0f}")
p3.metric("Expected by Now", f"${expected:,.0f}")
p4.metric(
    "Pace Variance",
    f"${abs(variance):,.0f}",
    delta=f"{'Under' if variance >= 0 else 'Over'} pace",
    delta_color="normal" if variance >= 0 else "inverse",
)
st.divider()

# -- Metric cards --
total = df["amount_abs"].sum()
days = max((df["date"].max() - df["date"].min()).days, 1)
daily_avg = total / days
top_cat = df.groupby("category")["amount_abs"].sum().idxmax() if len(df) > 0 else "---"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Expenses", f"${total:,.2f}")
c2.metric("Daily Average", f"${daily_avg:,.2f}")
c3.metric("Transactions", f"{len(df)}")
c4.metric("Top Category", top_cat)

# -- Charts row --
col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("Spending by Category")
    cat_totals = (
        df.groupby("category")["amount_abs"]
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .reset_index()
    )
    if len(cat_totals) > 0:
        fig = px.pie(
            cat_totals,
            values="amount_abs",
            names="category",
            hole=0.45,
            color="category",
            color_discrete_map=dict(zip(cat_totals["category"], get_color_sequence(cat_totals["category"].tolist()))),
        )
        fig.update_layout(**PLOTLY_LAYOUT, showlegend=True, height=350)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Source Split")
    source_totals = df.groupby("source")["amount_abs"].sum().reset_index()
    if len(source_totals) > 0:
        fig2 = px.pie(
            source_totals,
            values="amount_abs",
            names="source",
            hole=0.5,
            color="source",
            color_discrete_sequence=["#4C78A8", "#E45756"],
        )
        fig2.update_layout(**PLOTLY_LAYOUT, showlegend=True, height=350)
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True)

# -- Recent transactions table --
st.subheader("Recent Transactions")
recent = df.sort_values("date", ascending=False).head(15).copy()
recent["date"] = recent["date"].dt.strftime("%m/%d/%Y")
recent["amount"] = recent["amount"].apply(lambda x: f"${x:,.2f}")
st.dataframe(
    recent[["date", "description", "amount", "category", "source"]],
    use_container_width=True,
    hide_index=True,
)
