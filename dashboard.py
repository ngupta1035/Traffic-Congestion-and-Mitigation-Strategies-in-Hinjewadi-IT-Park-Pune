import streamlit as st
import pandas as pd
import time
import os

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="Traffic Congestion Dashboard", layout="centered")

st.title("🚦 Traffic Congestion Monitoring Dashboard")
st.write("Real-time traffic congestion analysis using AI-based vehicle detection")

CSV_PATH = "data/traffic_data.csv"

# -----------------------------
# CHECK IF CSV EXISTS
# -----------------------------
if not os.path.exists(CSV_PATH):
    st.warning("⚠️ Traffic data not found. Please run detect_traffic.py first.")
    st.stop()

# -----------------------------
# AUTO REFRESH
# -----------------------------
refresh_rate = 3  # seconds

placeholder = st.empty()

while True:
    with placeholder.container():
        # Load data
        df = pd.read_csv(CSV_PATH)

        if df.empty:
            st.info("Waiting for traffic data...")
        else:
            # Latest values
            latest = df.iloc[-1]

            col1, col2, col3 = st.columns(3)

            col1.metric("🚗 Vehicle Count", int(latest["Vehicle_Count"]))
            col2.metric("⏱ Time", latest["Time"])
            col3.metric("🚦 Congestion", latest["Congestion_Level"])

            st.subheader("📈 Traffic Trend")
            st.line_chart(df["Vehicle_Count"])

            st.subheader("📄 Traffic Data")
            st.dataframe(df.tail(10))

    time.sleep(refresh_rate)
