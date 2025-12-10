"""
Simple Dashboard for Tomorrow's Demo
Shows real-time health monitoring data from database
Member C: Visualization
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime, timedelta
import sys

# Add parent directory to path
sys.path.append('.')

from src.db_manager import DatabaseManager

# Page config
st.set_page_config(
    page_title="IoT Health Monitor",
    page_icon="🏥",
    layout="wide"
)

# Initialize database
@st.cache_resource
def get_db():
    return DatabaseManager()

db = get_db()

# Title
st.title("🏥 IoT Health Monitoring System")
st.markdown("**Real-time Anomaly Detection with AI**")
st.markdown("---")

# Auto-refresh setup
auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 1, 10, 2)

# Stats in sidebar
st.sidebar.markdown("### 📊 Statistics")

try:
    stats = db.get_statistics()
    
    if stats and stats.get('total_records', 0) > 0:
        total_records = int(stats.get('total_records', 0) or 0)
        total_anomalies = int(stats.get('total_anomalies', 0) or 0)
        avg_hr = float(stats.get('avg_hr', 0) or 0)
        avg_spo2 = float(stats.get('avg_spo2', 0) or 0)

        st.sidebar.metric("Total Records", total_records)
        st.sidebar.metric("Total Anomalies", total_anomalies)
        st.sidebar.metric("Avg Heart Rate", f"{avg_hr:.1f} bpm")
        st.sidebar.metric("Avg SpO2", f"{avg_spo2:.1f}%")
        
        # Anomaly count last 24h
        anomaly_24h = db.get_anomaly_count(hours=24)
        st.sidebar.metric("Anomalies (24h)", anomaly_24h)
    else:   
        st.sidebar.info("No data yet. Start the simulator!")
        
except Exception as e:
    st.sidebar.error(f"Database error: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 System Status")
st.sidebar.success("✓ Database Connected")
st.sidebar.info("ℹ️ Waiting for sensor data...")

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📈 Real-Time Monitoring")
    chart_container = st.empty()

with col2:
    st.subheader("⚠️ Recent Anomalies")
    anomaly_container = st.empty()

# Data table
st.subheader("📋 Recent Readings")
table_container = st.empty()

# Function to create charts
def create_charts(data_df):
    """Create interactive charts"""
    if data_df.empty:
        return None
    
    # Sort by timestamp
    data_df = data_df.sort_values('timestamp')
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Heart Rate (bpm)', 'Blood Oxygen (SpO2 %)'),
        vertical_spacing=0.15
    )
    
    # Separate normal and anomalous data
    normal_data = data_df[data_df['is_anomaly'] == 0]
    anomaly_data = data_df[data_df['is_anomaly'] == 1]
    
    # Heart Rate plot
    if not normal_data.empty:
        fig.add_trace(
            go.Scatter(
                x=normal_data['timestamp'],
                y=normal_data['hr'],
                mode='lines+markers',
                name='Normal HR',
                line=dict(color='blue', width=2),
                marker=dict(size=6)
            ),
            row=1, col=1
        )
    
    if not anomaly_data.empty:
        fig.add_trace(
            go.Scatter(
                x=anomaly_data['timestamp'],
                y=anomaly_data['hr'],
                mode='markers',
                name='Anomaly HR',
                marker=dict(color='red', size=12, symbol='x')
            ),
            row=1, col=1
        )
    
    # SpO2 plot
    if not normal_data.empty:
        fig.add_trace(
            go.Scatter(
                x=normal_data['timestamp'],
                y=normal_data['spo2'],
                mode='lines+markers',
                name='Normal SpO2',
                line=dict(color='green', width=2),
                marker=dict(size=6)
            ),
            row=2, col=1
        )
    
    if not anomaly_data.empty:
        fig.add_trace(
            go.Scatter(
                x=anomaly_data['timestamp'],
                y=anomaly_data['spo2'],
                mode='markers',
                name='Anomaly SpO2',
                marker=dict(color='red', size=12, symbol='x')
            ),
            row=2, col=1
        )
    
    # Add reference lines
    fig.add_hline(y=60, line_dash="dash", line_color="gray", row=1, col=1)
    fig.add_hline(y=100, line_dash="dash", line_color="gray", row=1, col=1)
    fig.add_hline(y=95, line_dash="dash", line_color="gray", row=2, col=1)
    
    # Update layout
    fig.update_layout(
        height=600,
        showlegend=True,
        hovermode='x unified'
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="BPM", row=1, col=1)
    fig.update_yaxes(title_text="SpO2 %", row=2, col=1)
    
    return fig

# Main loop
placeholder = st.empty()

while True:
    try:
        # Fetch latest data
        records = db.get_latest_records(limit=50)
        
        if records:
            df = pd.DataFrame(records)
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Display charts
            with chart_container:
                fig = create_charts(df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Waiting for data...")
            
            # Display recent anomalies
            with anomaly_container:
                anomalies = db.get_recent_anomalies(limit=5)
                if anomalies:
                    for i, anom in enumerate(anomalies):
                        timestamp = pd.to_datetime(anom['timestamp']).strftime('%H:%M:%S')
                        st.error(f"🚨 {timestamp}")
                        st.write(f"HR: {anom['hr']} | SpO2: {anom['spo2']}%")
                        if i < len(anomalies) - 1:
                            st.markdown("---")
                else:
                    st.success("✓ No recent anomalies")
            
            # Display data table
            with table_container:
                display_df = df[['timestamp', 'hr', 'spo2', 'is_anomaly']].head(10)
                display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                display_df['Status'] = display_df['is_anomaly'].apply(
                    lambda x: '🚨 Anomaly' if x == 1 else '✓ Normal'
                )
                display_df = display_df[['timestamp', 'hr', 'spo2', 'Status']]
                display_df.columns = ['Timestamp', 'Heart Rate', 'SpO2 %', 'Status']
                st.dataframe(display_df, use_container_width=True)
        
        else:
            with chart_container:
                st.info("📡 No data received yet. Please start the sensor simulator.")
                st.code("python src/sensor_sim.py", language="bash")
    
    except Exception as e:
        st.error(f"Error: {e}")
    
    # Auto refresh
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()
    else:
        break