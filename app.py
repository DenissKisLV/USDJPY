import streamlit as st
import pandas as pd
import requests
import ta

# Title
st.title("USD/JPY Signal Generator")
st.caption("EMA(9/21) + RSI(14) strategy (No charts)")

# Fetch data from Twelve data
@st.cache_data(ttl=3600)
def get_data():
    API_KEY = "16e5ff0d354c4d0e9a97393a92583513" # replace this
    SYMBOL = "USD/JPY"
    INTERVAL = "1h"
    URL = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval={INTERVAL}&outputsize=1000&apikey={API_KEY}"

    r = requests.get(URL)
    raw = r.json()

    if "values" not in raw:
        st.write(raw)  # helpful for debugging
        return None

    df = pd.DataFrame(raw["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df = df.rename(columns={
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close"
    })
    df = df.astype(float)
    df = df.sort_index()
    return df

df = get_data()

if df is None:
    st.error("Failed to fetch data. Check your API key or try again later.")
    st.stop()

# Calculate indicators
df["EMA_9"] = ta.trend.ema_indicator(df["close"], window=9)
df["EMA_21"] = ta.trend.ema_indicator(df["close"], window=21)
df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

# Generate signals
def generate_signals(df):
    signals = []
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        buy = (
            row["EMA_9"] > row["EMA_21"]
            and row["close"] > row["EMA_9"]
            and 40 < row["RSI"] < 60
            and row["RSI"] > prev["RSI"]
        )

        sell = (
            row["EMA_9"] < row["EMA_21"]
            and row["close"] < row["EMA_9"]
            and 40 < row["RSI"] < 60
            and row["RSI"] < prev["RSI"]
        )

        if buy:
            signals.append("Buy")
        elif sell:
            signals.append("Sell")
        else:
            signals.append("Hold")
    signals.insert(0, "Hold")
    df["Signal"] = signals
    return df

df = generate_signals(df)

# Display latest signals
st.subheader("Latest Signal")
latest_row = df.iloc[-1]
st.write(f"**Time:** {latest_row.name}")
st.write(f"**Price:** {latest_row['close']:.3f}")
st.write(f"**Signal:** {latest_row['Signal']}")

# Show table
st.subheader("Recent Data")
st.dataframe(df.tail(10)[["close", "EMA_9", "EMA_21", "RSI", "Signal"]])
