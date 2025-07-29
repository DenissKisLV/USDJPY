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

def backtest(df, initial_capital=50000, position_size_pct=0.05, tp=0.06, sl=0.02, fee_rate=FEE_RATE):
    capital = initial_capital
    in_position = False
    position_type = None
    trades = []

    for i in range(len(df)):
        row = df.iloc[i]

        if row["Signal"] in ["Buy", "Sell"] and not in_position:
            entry_time = row.name
            entry_price = row["close"]
            direction = 1 if row["Signal"] == "Buy" else -1
            investment = capital * position_size_pct
            units = investment / entry_price
            in_position = True
            position_type = row["Signal"]

            for j in range(i + 1, len(df)):
                next_row = df.iloc[j]
                price_change = (next_row["close"] - entry_price) / entry_price * direction

                if price_change >= tp or price_change <= -sl:
                    exit_time = next_row.name
                    exit_price = next_row["close"]
                    gross_pnl = (exit_price - entry_price) * units * direction
                    fee = investment * fee_rate
                    net_pnl = gross_pnl - fee
                    pct_change = (net_pnl / investment) * 100

                    trades.append({
                        "Entry Time": entry_time,
                        "Exit Time": exit_time,
                        "Position": position_type,
                        "Entry Price": round(entry_price, 3),
                        "Exit Price": round(exit_price, 3),
                        "EMA_9": round(row["EMA_9"], 3),
                        "EMA_21": round(row["EMA_21"], 3),
                        "RSI": round(row["RSI"], 2),
                        "Invested (€)": round(investment, 2),
                        "Profit/Loss (€)": round(net_pnl, 2),
                        "Profit/Loss (%)": round(pct_change, 2),
                        "Fee (€)": round(fee, 2)
                    })

                    capital += net_pnl
                    in_position = False
                    break

    return pd.DataFrame(trades)

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
        # Rearranged detailed columns
    results["Units"] = results["Invested (€)"] / results["Entry Price"]
    results["EUR Acquired"] = results["Invested (€)"] + results["Profit/Loss (€)"]

    trade_log = results[[
        "Entry Time", "Entry Price", "Units", "Invested (€)",
        "Exit Time", "Exit Price", "EUR Acquired",
        "Profit/Loss (€)", "Profit/Loss (%)"
    ]].copy()

    st.dataframe(trade_log, use_container_width=True)

        # Download CSV
    csv = trade_log.to_csv(index=False).encode("utf-8")
    st.download_button("📁 Download Trade Log (CSV)", csv, "usd_jpy_trades.csv", "text/csv")
    
