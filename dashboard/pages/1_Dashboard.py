"""Category Breakdown -- donut, bar, and stacked weekly charts."""

import streamlit as st
import plotly.express as px
import pandas as pd
from utils.data_loader import load_expenses, filter_by_dates
from utils.charts import get_color_sequence, PLOTLY_LAYOUT

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("Category Breakdown")

# -- Load & filter --
expenses = load_expenses()
date_range = st.session_state.get("date_range")
if isinstance(date_range, tuple) and len(date_range) == 2:
    df = filter_by_dates(expenses, date_range[0], date_range[1])
else:
    df = expenses.copy()

if len(df) == 0:
    st.warning("No transactions in selected date range.")
    st.stop()

cat_totals = (
    df.groupby("category")["amount_abs"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)
colors = get_color_sequence(cat_totals["category"].tolist())
color_map = dict(zip(cat_totals["category"], colors))

# -- Row 1: Donut + Horizontal Bar --
col1, col2 = st.columns(2)

with col1:
    st.subheader("Spending Distribution")
    fig_donut = px.pie(
        cat_totals,
        values="amount_abs",
        names="category",
        hole=0.45,
        color="category",
        color_discrete_map=color_map,
    )
    fig_donut.update_layout(**PLOTLY_LAYOUT, showlegend=False, height=420)
    fig_donut.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_donut, use_container_width=True)

with col2:
    st.subheader("Category Totals")
    cat_sorted = cat_totals.sort_values("amount_abs", ascending=True)
    fig_bar = px.bar(
        cat_sorted,
        x="amount_abs",
        y="category",
        orientation="h",
        color="category",
        color_discrete_map=color_map,
        text=cat_sorted["amount_abs"].apply(lambda x: f"${x:,.0f}"),
    )
    fig_bar.update_layout(**PLOTLY_LAYOUT, showlegend=False, height=420, yaxis_title="")
    fig_bar.update_traces(textposition="outside")
    st.plotly_chart(fig_bar, use_container_width=True)

# -- Row 2: Stacked bar by week --
st.subheader("Weekly Spending by Category")
df_week = df.copy()
df_week["week"] = df_week["date"].dt.isocalendar().week.astype(int)
df_week["week_start"] = df_week["date"].dt.to_period("W").apply(lambda p: p.start_time)

top_cats = cat_totals.head(6)["category"].tolist()
df_week["cat_group"] = df_week["category"].where(df_week["category"].isin(top_cats), "Other")

weekly = (
    df_week.groupby(["week_start", "cat_group"])["amount_abs"]
    .sum()
    .reset_index()
)

fig_stack = px.bar(
    weekly,
    x="week_start",
    y="amount_abs",
    color="cat_group",
    color_discrete_map={**color_map, "Other": "#79706E"},
    labels={"week_start": "Week", "amount_abs": "Amount ($)", "cat_group": "Category"},
)
fig_stack.update_layout(**PLOTLY_LAYOUT, barmode="stack", height=400)
st.plotly_chart(fig_stack, use_container_width=True)
