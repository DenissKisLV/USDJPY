import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import ta

# ---------------------------
# Configuration
# ---------------------------
st.set_page_config(page_title="USD/JPY Signal Tool", layout="wide")
st.title("📈 USD/JPY Signal Generator (EMA + RSI Strategy)")

# ---------------------------
# Data Fetching
# ---------------------------
@st.cache_data(ttl=3600)
def get_fx_data():
    API_KEY = "demo"  # Replace with your Alpha Vantage API key
    SYMBOL = "USDJPY"
    INTERVAL = "60min"

    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=USD&to_symbol=JPY&interval={INTERVAL}&outputsize=full&apikey={API_KEY}"
    r = requests.get(url)
    data = r.json().get(f"Time Series FX ({INTERVAL})", {})

    if not data:
        return None

    df = pd.DataFrame(data).T
    df = df.rename(columns={
        '1. open': 'open',
        '2. high': 'high',
        '3. low': 'low',
        '4. close': 'close'
    })
    df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    return df

df = get_fx_data()
if df is None:
    st.error("Failed to fetch data.")
    st.stop()

# ---------------------------
# Indicator Calculation
# ---------------------------
df['EMA_9'] = ta.trend.ema_indicator(df['close'], window=9)
df['EMA_21'] = ta.trend.ema_indicator(df['close'], window=21)
df['RSI'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

# ---------------------------
# Signal Generation
# ---------------------------
def generate_signals(df):
    signals = []
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]

        buy = (
            row['EMA_9'] > row['EMA_21']
            and row['close'] > row['EMA_9']
            and row['RSI'] > 40 and row['RSI'] < 60 and row['RSI'] > prev['RSI']
        )

        sell = (
            row['EMA_9'] < row['EMA_21']
            and row['close'] < row['EMA_9']
            and row['RSI'] < 60 and row['RSI'] > 40 and row['RSI'] < prev['RSI']
        )

        if buy:
            signals.append("Buy")
        elif sell:
            signals.append("Sell")
        else:
            signals.append("Hold")
    signals.insert(0, "Hold")
    df['Signal'] = signals
    return df

df = generate_signals(df)

# ---------------------------
# Candlestick Chart with Signals
# ---------------------------
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df.index,
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name="USD/JPY"
))

fig.add_trace(go.Scatter(
    x=df.index, y=df['EMA_9'], line=dict(color='blue', width=1), name="EMA 9"
))
fig.add_trace(go.Scatter(
    x=df.index, y=df['EMA_21'], line=dict(color='orange', width=1), name="EMA 21"
))

# Signal markers
buy_signals = df[df['Signal'] == 'Buy']
sell_signals = df[df['Signal'] == 'Sell']

fig.add_trace(go.Scatter(
    x=buy_signals.index,
    y=buy_signals['low'],
    mode='markers',
    marker=dict(color='green', size=8, symbol='arrow-up'),
    name='Buy Signal'
))

fig.add_trace(go.Scatter(
    x=sell_signals.index,
    y=sell_signals['high'],
    mode='markers',
    marker=dict(color='red', size=8, symbol='arrow-down'),
    name='Sell Signal'
))

fig.update_layout(height=600, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# RSI Line Chart
# ---------------------------
st.subheader("RSI (14)")
st.line_chart(df[['RSI']])
