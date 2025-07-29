import streamlit as st
import pandas as pd
import requests
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

# ===================== CONFIG =====================
API_KEY = "16e5ff0d354c4d0e9a97393a92583513"  # Replace with your Twelve Data key
SYMBOL = "USD/JPY"
INTERVAL = "1h"
FEE_RATE = 0.0003  # 0.03% fee per trade (round trip)
# ===================================================

st.title("USD/JPY Signal & Backtest Simulator")

@st.cache_data(ttl=3600)
def get_data():
    url = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval={INTERVAL}&outputsize=5000&apikey={API_KEY}"
    r = requests.get(url)
    raw = r.json()

    if "values" not in raw:
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

def generate_signals(df):
    df["EMA_9"] = EMAIndicator(df["close"], window=9).ema_indicator()
    df["EMA_21"] = EMAIndicator(df["close"], window=21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], window=14).rsi()
    
    df["Signal"] = "Hold"
    df.loc[(df["EMA_9"] > df["EMA_21"]) & (df["RSI"] < 70), "Signal"] = "Buy"
    df.loc[(df["EMA_9"] < df["EMA_21"]) & (df["RSI"] > 30), "Signal"] = "Sell"
    return df

def backtest(df):
    initial_capital = 50000
    max_position_pct = 0.05
    trade_fee_pct = 0.001  # 0.1%

    position = None
    entry_price = 0
    entry_time = None
    capital = initial_capital
    results = []
    last_trade_date = None

    for i in range(len(df)):
        row = df.iloc[i]
        current_date = row.name.date()
        price = row["close"]
        signal = row["Signal"]

        if signal in ["Buy", "Sell"]:
            # Restrict to one trade per day
            if last_trade_date == current_date:
                continue

            position = {
                "type": signal,
                "entry_price": price,
                "entry_time": row.name,
                "capital_allocated": capital * max_position_pct,
                "units": (capital * max_position_pct) / price,
            }
            last_trade_date = current_date
            continue

        if position:
            # Check exit conditions
            change = (price - position["entry_price"]) / position["entry_price"]
            if position["type"] == "Sell":
                change = -change  # Invert for short

            if change >= 0.06 or change <= -0.02:
                gross_return = position["capital_allocated"] * (1 + change)
                fee = (position["capital_allocated"] + gross_return) * trade_fee_pct
                net_return = gross_return - fee
                profit = net_return - position["capital_allocated"]
                pct_return = (profit / position["capital_allocated"]) * 100

                results.append({
                    "Entry Time": position["entry_time"],
                    "Exit Time": row.name,
                    "Profit/Loss (€)": profit,
                    "Profit/Loss (%)": pct_return
                })

                capital += profit
                position = None

    return pd.DataFrame(results)
# ========== RUN APP ==========
with st.spinner("Fetching USD/JPY data..."):
    df = get_data()

if df is None:
    st.error("Failed to fetch data. Check API key or try again later.")
else:
    df = generate_signals(df)
st.subheader("Latest Signal")

latest_time = df.index[-1]
latest = df.iloc[-1]

st.metric("Signal", latest["Signal"])
st.write(f"📅 Datetime: {latest_time}")
st.write(f"📈 EMA-9: {latest['EMA_9']:.3f}, EMA-21: {latest['EMA_21']:.3f}")
st.write(f"📉 RSI: {latest['RSI']:.2f}")

    # 🟢 Show all Buy/Sell signals
st.subheader("📋 Buy/Sell Signal List")
signal_df = df[df["Signal"].isin(["Buy", "Sell"])][["Signal", "close"]]
signal_df["Datetime"] = signal_df.index
signal_df = signal_df[["Datetime", "Signal", "close"]]
signal_df = signal_df.rename(columns={"close": "Price"})
st.dataframe(signal_df, use_container_width=True)

    # 🔁 Backtest Results
st.subheader("📈 Simulated Trades")

results = backtest(df)

if results.empty:
        st.info("No trades triggered.")
    else:
        # Days held
        results["Days Held"] = (pd.to_datetime(results["Exit Time"]) - pd.to_datetime(results["Entry Time"])).dt.days

        summary_df = results[[
            "Entry Time", "Exit Time", "Days Held", "Profit/Loss (%)"
        ]].copy()

        st.dataframe(summary_df, use_container_width=True)

        # Capital summary
        initial_capital = 50000
        final_capital = initial_capital + results["Profit/Loss (€)"].sum()
        average_return = results["Profit/Loss (%)"].mean()

        st.markdown(f"**💰 Initial Capital:** €{initial_capital:,.2f}")
        st.markdown(f"**🏁 Final Capital:** €{final_capital:,.2f}")
        st.markdown(f"**📊 Average Trade Return:** {average_return:.2f}%")
