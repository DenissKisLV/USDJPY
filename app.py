import streamlit as st
import pandas as pd
import yfinance as yf
import ta

st.set_page_config(layout="wide")
st.title("USD/JPY Signal Generator and Backtester (Yahoo Finance)")

@st.cache_data
def fetch_data():
    symbol = "JPY=X"  # Yahoo Finance symbol for USD/JPY
    df = yf.download(symbol, period="5y", interval="1d")  # 5 years of hourly data
    df.index = pd.to_datetime(df.index)
    return df

def generate_signals(df):
    df["EMA_9"] = ta.trend.ema_indicator(df["Close"], window=9)
    df["EMA_21"] = ta.trend.ema_indicator(df["Close"], window=21)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)

    df["Signal"] = "Hold"
    df["Prev_EMA_9"] = df["EMA_9"].shift(1)
    df["Prev_EMA_21"] = df["EMA_21"].shift(1)

    for i in range(1, len(df)):
        if (
            df["Prev_EMA_9"].iloc[i] < df["Prev_EMA_21"].iloc[i]
            and df["EMA_9"].iloc[i] > df["EMA_21"].iloc[i]
            and df["RSI"].iloc[i] < 70
        ):
            df.at[df.index[i], "Signal"] = "Buy"
        elif (
            df["Prev_EMA_9"].iloc[i] > df["Prev_EMA_21"].iloc[i]
            and df["EMA_9"].iloc[i] < df["EMA_21"].iloc[i]
            and df["RSI"].iloc[i] > 30
        ):
            df.at[df.index[i], "Signal"] = "Sell"

    # Restrict to 1 signal per day
    df["Date"] = df.index.date
    df["Signal_Rank"] = df.groupby("Date")["Signal"].transform(
        lambda x: (x != "Hold").cumsum()
    )
    df = df[df["Signal_Rank"] <= 1]
    df = df.drop(columns=["Date", "Signal_Rank", "Prev_EMA_9", "Prev_EMA_21"])

    return df

def backtest(df):
    initial_capital = 50000
    max_position_pct = 0.05
    fee_pct = 0.001  # 0.1% total round-trip fee
    capital = initial_capital
    position = None
    results = []
    last_trade_date = None

    for i in range(len(df)):
        row = df.iloc[i]
        price = row["Close"]
        signal = row["Signal"]
        current_date = row.name.date()

        # Entry
        if signal in ["Buy", "Sell"]:
            if last_trade_date == current_date:
                continue  # only one trade per day
            capital_allocated = capital * max_position_pct
            units = capital_allocated / price
            entry_price = price
            entry_time = row.name
            position = {
                "type": signal,
                "entry_price": entry_price,
                "entry_time": entry_time,
                "capital_allocated": capital_allocated,
                "units": units,
            }
            last_trade_date = current_date
            continue

        # Exit
        if position:
            change = (price - position["entry_price"]) / position["entry_price"]
            if position["type"] == "Sell":
                change = -change
            if change >= 0.06 or change <= -0.02:
                gross_return = position["capital_allocated"] * (1 + change)
                fee = (position["capital_allocated"] + gross_return) * fee_pct
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

# ========== Streamlit Interface ==========

df = fetch_data()

if df is None or df.empty:
    st.error("❌ Failed to fetch data.")
else:
    df = generate_signals(df)

    st.subheader("Latest Signal")
    latest_time = df.index[-1]
    latest = df.iloc[-1]
    st.metric("Signal", latest["Signal"])
    st.write(f"🕒 Timestamp: {latest_time}")
    st.write(f"EMA-9: {latest['EMA_9']:.3f}, EMA-21: {latest['EMA_21']:.3f}")
    st.write(f"RSI: {latest['RSI']:.2f}")

    # Signal Table (1 per day)
    st.subheader("📋 Signal List (Max 1/day)")
    signals = df[df["Signal"].isin(["Buy", "Sell"])]
    signal_list = signals[["Signal", "Close"]].copy()
    signal_list["Timestamp"] = signals.index
    signal_list.rename(columns={"Close": "Price"}, inplace=True)
    st.dataframe(signal_list[["Timestamp", "Signal", "Price"]], use_container_width=True)

    # Backtest Results
    st.subheader("📈 Backtest Results")
    results = backtest(df)

    if results.empty:
        st.info("No trades executed during this period.")
    else:
        results["Days Held"] = (
            pd.to_datetime(results["Exit Time"]) - pd.to_datetime(results["Entry Time"])
        ).dt.days

        summary_df = results[[
            "Entry Time", "Exit Time", "Days Held", "Profit/Loss (%)"
        ]]
        st.dataframe(summary_df, use_container_width=True)

        initial_capital = 50000
        final_capital = initial_capital + results["Profit/Loss (€)"].sum()
        avg_return = results["Profit/Loss (%)"].mean()

        st.markdown(f"**💰 Initial Capital:** €{initial_capital:,.2f}")
        st.markdown(f"**🏁 Final Capital:** €{final_capital:,.2f}")
        st.markdown(f"**📊 Average Trade Return:** {avg_return:.2f}%")
