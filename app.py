import streamlit as st
import pandas as pd
import yfinance as yf
import ta

# App title
st.title("USD/JPY Signal Generator and Backtester (Yahoo Finance)")

# Initial capital and config
initial_capital = 50000
position_size_pct = 0.05
take_profit = 0.06
stop_loss = 0.02
fee_rate = 0.001  # 0.1%

# Fetch data
@st.cache_data
def fetch_data():
    symbol = "JPY=X"
    df = yf.download(symbol, period="5y", interval="1d")

    if df.empty:
        st.error("Downloaded data is empty.")
        return None

    # Fallback to Adj Close
    if "Close" not in df.columns:
        if "Adj Close" in df.columns:
            df["Close"] = df["Adj Close"]
        else:
            st.error("No Close or Adj Close column found.")
            return None

    df = df.dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index)
    return df


# Generate Buy/Sell signals
def generate_signals(df):
    df = df.copy()
    df = df.dropna(subset=["Close"])

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

    # Limit to one signal per day
    df["Signal_Rank"] = df["Signal"].ne("Hold").groupby(df.index.date).cumsum()
    df = df[(df["Signal"] != "Hold") & (df["Signal_Rank"] == 1)]
    df.drop(columns=["Prev_EMA_9", "Prev_EMA_21", "Signal_Rank"], inplace=True)

    return df


# Simulate trading
def simulate_trades(df):
    capital = initial_capital
    trades = []
    last_trade_date = None

    for i in range(len(df)):
        row = df.iloc[i]
        signal_date = df.index[i].date()
        price = row["Close"]

        # Only one trade per day
        if signal_date == last_trade_date:
            continue
        last_trade_date = signal_date

        position_type = row["Signal"]
        volume = (capital * position_size_pct) / price
        entry_price = price
        entry_time = df.index[i]

        # Search for exit
        for j in range(i + 1, len(df)):
            exit_price = df["Close"].iloc[j]
            change = (exit_price - entry_price) / entry_price
            if position_type == "Sell":
                change = -change  # inverse for shorts

            if change >= take_profit or change <= -stop_loss:
                exit_time = df.index[j]
                gross_return = change
                pnl = volume * entry_price * gross_return
                fees = (volume * entry_price + volume * exit_price) * fee_rate
                net_pnl = pnl - fees
                capital += net_pnl

                trades.append({
                    "Entry Time": entry_time,
                    "Exit Time": exit_time,
                    "Days Held": (exit_time - entry_time).days,
                    "Return %": round(gross_return * 100, 2),
                })
                break

    return trades, capital


# Run the app
df = fetch_data()
if df is not None:
    signal_df = generate_signals(df)
    st.subheader("Latest Signal")
    if not signal_df.empty:
        st.write(signal_df.iloc[-1][["Signal", "Close", "RSI"]])

    st.subheader("Signal List (Buy/Sell Only)")
    st.dataframe(signal_df[["Signal", "Close"]].rename(columns={"Close": "Price"}))

    st.subheader("Backtest Results")
    trades, final_capital = simulate_trades(signal_df)
    trade_df = pd.DataFrame(trades)

    if not trade_df.empty:
        avg_return = trade_df["Return %"].mean().round(2)
        st.dataframe(trade_df)
        st.markdown(f"**Initial Capital:** €{initial_capital:,.2f}")
        st.markdown(f"**Final Capital:** €{final_capital:,.2f}")
        st.markdown(f"**Average Return per Trade:** {avg_return:.2f}%")
    else:
        st.write("No trades were triggered based on the signals.")
