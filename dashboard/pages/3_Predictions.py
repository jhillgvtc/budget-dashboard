"""Forecast -- Prophet (primary) with Holt-Winters fallback."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from utils.data_loader import load_expenses, filter_by_dates
from utils.charts import PLOTLY_LAYOUT

st.set_page_config(page_title="Predictions", page_icon="🔮", layout="wide")
st.title("Spending Forecast")

st.warning(
    "**Disclaimer:** This forecast is based on ~6 weeks of transaction data. "
    "Treat predictions as directional estimates, not financial advice."
)

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

# -- Prepare daily time series --
daily = df.groupby(df["date"].dt.date)["amount_abs"].sum().reset_index()
daily.columns = ["date", "amount"]
daily["date"] = pd.to_datetime(daily["date"])
daily = daily.set_index("date").resample("D").sum().fillna(0).reset_index()

# -- Controls --
horizon = st.slider("Forecast horizon (days)", min_value=7, max_value=90, value=30, step=7)

# -- Try Prophet, fallback to Holt-Winters --
forecast_df = None
method_used = None

try:
    from prophet import Prophet
    import logging
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    prophet_df = daily.rename(columns={"date": "ds", "amount": "y"})
    m = Prophet(
        daily_seasonality=False,
        yearly_seasonality=False,
        weekly_seasonality=True,
        interval_width=0.80,
    )
    m.fit(prophet_df)
    future = m.make_future_dataframe(periods=horizon)
    forecast = m.predict(future)

    forecast_df = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    forecast_df = forecast_df.rename(columns={"ds": "date", "yhat": "predicted"})
    # Clamp negatives to zero (can't have negative daily spending)
    forecast_df["predicted"] = forecast_df["predicted"].clip(lower=0)
    forecast_df["yhat_lower"] = forecast_df["yhat_lower"].clip(lower=0)
    forecast_df["yhat_upper"] = forecast_df["yhat_upper"].clip(lower=0)
    method_used = "Prophet"

except Exception:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    y = daily["amount"].values
    if len(y) < 14:
        st.error("Not enough data for forecasting (need at least 14 days).")
        st.stop()

    seasonal_periods = 7
    model = ExponentialSmoothing(
        y,
        trend="add",
        seasonal="add",
        seasonal_periods=seasonal_periods,
    ).fit(optimized=True)

    pred = model.forecast(horizon)
    pred = np.clip(pred, 0, None)

    # Build confidence interval using residual std
    residuals = y - model.fittedvalues
    std = residuals.std()
    future_dates = pd.date_range(daily["date"].iloc[-1] + pd.Timedelta(days=1), periods=horizon)

    forecast_future = pd.DataFrame({
        "date": future_dates,
        "predicted": pred,
        "yhat_lower": np.clip(pred - 1.28 * std, 0, None),
        "yhat_upper": pred + 1.28 * std,
    })

    # Combine historical fitted values
    hist_fitted = pd.DataFrame({
        "date": daily["date"],
        "predicted": np.clip(model.fittedvalues, 0, None),
        "yhat_lower": np.clip(model.fittedvalues - 1.28 * std, 0, None),
        "yhat_upper": model.fittedvalues + 1.28 * std,
    })

    forecast_df = pd.concat([hist_fitted, forecast_future], ignore_index=True)
    method_used = "Holt-Winters"

st.caption(f"Method: **{method_used}**")

# -- Metrics --
future_only = forecast_df[forecast_df["date"] > daily["date"].max()]
predicted_30d = future_only.head(30)["predicted"].sum()
predicted_horizon = future_only["predicted"].sum()

m1, m2, m3 = st.columns(3)
m1.metric("Predicted Next 30 Days", f"${predicted_30d:,.0f}")
m2.metric(f"Predicted Next {horizon} Days", f"${predicted_horizon:,.0f}")
m3.metric("Avg Daily (Forecast)", f"${future_only['predicted'].mean():,.0f}")

# -- Forecast chart --
st.subheader("Forecast")
fig = go.Figure()

# Historical actuals
fig.add_trace(go.Scatter(
    x=daily["date"], y=daily["amount"],
    mode="lines",
    name="Actual",
    line=dict(color="#4C78A8", width=2),
))

# Forecast line
fig.add_trace(go.Scatter(
    x=future_only["date"], y=future_only["predicted"],
    mode="lines",
    name="Forecast",
    line=dict(color="#E45756", width=2, dash="dash"),
))

# Confidence band
fig.add_trace(go.Scatter(
    x=pd.concat([future_only["date"], future_only["date"][::-1]]),
    y=pd.concat([future_only["yhat_upper"], future_only["yhat_lower"][::-1]]),
    fill="toself",
    fillcolor="rgba(228,87,86,0.15)",
    line=dict(color="rgba(0,0,0,0)"),
    name="80% Confidence",
))

fig.update_layout(
    **PLOTLY_LAYOUT,
    height=450,
    xaxis_title="",
    yaxis_title="Daily Spending ($)",
    showlegend=True,
)
st.plotly_chart(fig, use_container_width=True)

# -- Weekly seasonality (if Prophet) --
if method_used == "Prophet":
    try:
        st.subheader("Weekly Seasonality Pattern")
        from prophet.plot import plot_weekly
        weekly = m.predict(m.make_future_dataframe(periods=0))
        days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Extract weekly component
        weekly_comp = forecast_df.copy()
        weekly_comp = weekly_comp[weekly_comp["date"] <= daily["date"].max()]
        weekly_comp["dow"] = weekly_comp["date"].dt.dayofweek
        dow_avg = weekly_comp.groupby("dow")["predicted"].mean().reindex(range(7))

        fig_w = go.Figure()
        fig_w.add_trace(go.Bar(
            x=days_of_week,
            y=dow_avg.values,
            marker_color="#72B7B2",
        ))
        fig_w.update_layout(**PLOTLY_LAYOUT, height=300, yaxis_title="Avg Predicted ($)")
        st.plotly_chart(fig_w, use_container_width=True)
    except Exception:
        pass
