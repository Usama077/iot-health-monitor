# IoT Health Monitoring System

Real-time health monitoring with AI-powered anomaly detection.

## Quick Start

### 1. Setup
```bash
# Clone repository
git clone <your-repo-url>
cd IoT-Health-Monitor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Database
```bash
# Login to MySQL
sudo mysql -u root -p

# Run these commands in MySQL:
CREATE DATABASE health_monitor;
CREATE USER 'iot_user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON health_monitor.* TO 'iot_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. Update Config
Edit `config.json` and update:
- MySQL password
- Email credentials (for alerts)

### 4. Generate Training Data
```bash
python src/generate_training_data.py
```

### 5. Train AI Model
```bash
python src/train_model.py
```

### 6. Run System
```bash
# Terminal 1: Backend
python src/backend_core.py

# Terminal 2: Simulator
python src/sensor_sim.py

# Terminal 3: Dashboard
streamlit run src/dashboard.py
```

## Architecture
```
Sensor Simulator → MQTT Broker → Backend (AI) → MySQL
                                       ↓
                                  Email Alerts / Push Notification
                                       ↓
                                  Dashboard (Streamlit) & Android App
```

## Team Members
- Member A: IoT Infrastructure (MQTT, Database, Simulator)
- Member B: AI Model & Backend Logic
- Member C: Dashboard & Notifications

## Current Status

✅ Project structure created
✅ Database manager working
✅ MQTT client working
✅ Training data generated
⏳ Model training (Member B)
⏳ Addroid (Member B)
⏳ Sensor simulator (Member A)
⏳ Backend core (Member B)
⏳ Dashboard (Member C)
⏳ Email notifier (Member C)