"""Spending Trends -- daily/weekly aggregation, rolling average, cumulative, by category."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.data_loader import load_expenses, filter_by_dates
from utils.charts import get_color_sequence, PLOTLY_LAYOUT

st.set_page_config(page_title="Spending Trends", page_icon="📈", layout="wide")
st.title("Spending Trends")

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

# -- Controls --
agg = st.radio("Aggregation", ["Daily", "Weekly"], horizontal=True)
freq = "D" if agg == "Daily" else "W"

# -- Aggregate spending --
daily = df.groupby(df["date"].dt.date)["amount_abs"].sum().reset_index()
daily.columns = ["date", "amount"]
daily["date"] = pd.to_datetime(daily["date"])
daily = daily.set_index("date").resample("D").sum().fillna(0).reset_index()

if freq == "W":
    ts = daily.set_index("date").resample("W").sum().reset_index()
else:
    ts = daily.copy()

# -- Row 1: Spending over time with rolling average --
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"{agg} Spending")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ts["date"], y=ts["amount"],
        name=f"{agg} Total",
        marker_color="#4C78A8",
        opacity=0.6,
    ))
    if freq == "D" and len(daily) >= 7:
        rolling = daily.copy()
        rolling["ma7"] = rolling["amount"].rolling(7, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=rolling["date"], y=rolling["ma7"],
            name="7-day Avg",
            line=dict(color="#E45756", width=2),
        ))
    fig.update_layout(**PLOTLY_LAYOUT, height=380, showlegend=True,
                      xaxis_title="", yaxis_title="Amount ($)")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Cumulative Spending")
    cumulative = daily.copy()
    cumulative["cumsum"] = cumulative["amount"].cumsum()
    fig2 = px.area(
        cumulative, x="date", y="cumsum",
        labels={"cumsum": "Cumulative ($)", "date": ""},
    )
    fig2.update_traces(line_color="#54A24B", fillcolor="rgba(84,162,75,0.2)")
    fig2.update_layout(**PLOTLY_LAYOUT, height=380)
    st.plotly_chart(fig2, use_container_width=True)

# -- Row 2: Multi-line by top categories --
st.subheader("Trends by Category")
top_cats = df.groupby("category")["amount_abs"].sum().nlargest(5).index.tolist()
cat_daily = (
    df[df["category"].isin(top_cats)]
    .groupby([df["date"].dt.date, "category"])["amount_abs"]
    .sum()
    .reset_index()
)
cat_daily.columns = ["date", "category", "amount"]
cat_daily["date"] = pd.to_datetime(cat_daily["date"])

if freq == "W":
    cat_daily = (
        cat_daily.groupby([pd.Grouper(key="date", freq="W"), "category"])["amount"]
        .sum()
        .reset_index()
    )

colors = get_color_sequence(top_cats)
color_map = dict(zip(top_cats, colors))

fig3 = px.line(
    cat_daily, x="date", y="amount", color="category",
    color_discrete_map=color_map,
    labels={"amount": "Amount ($)", "date": "", "category": "Category"},
)
fig3.update_layout(**PLOTLY_LAYOUT, height=400)
st.plotly_chart(fig3, use_container_width=True)
