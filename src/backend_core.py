"""
Simplified Backend with FCM Push Notifications
Token stored in .env file - no HTTP registration needed
"""

import time
import json
import logging
import sys
import pickle
import numpy as np
import os
from datetime import datetime

# Add parent directory to path
sys.path.append('.')

from src.mqtt_client import MQTTClient
from src.db_manager import DatabaseManager
from src.fcm_manager import FCMManager
from config_loader import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleAIBackend:
    def __init__(self):
        """Initialize backend with Isolation Forest model and FCM"""
        self.config = get_config()
        self.db = DatabaseManager()
        self.mqtt_client = MQTTClient()
        
        # Android MQTT topics
        self.android_topics = {
            'sensor_data': 'health/android/sensor_data',
            'anomaly_alert': 'health/android/anomaly_alert',
            'device_status': 'health/android/device_status'
        }
        
        # Load AI model
        self.model = None
        self.scaler = None
        self.load_model()
        
        # Initialize FCM Manager
        self.fcm_manager = None
        self.device_token = None
        self.initialize_fcm()
        
        # Alert tracking
        self.hr_anomaly_count = 0
        self.spo2_anomaly_count = 0
        
        # Configuration
        ai_config = self.config.get_section('ai_model')
        self.consecutive_alerts = ai_config['consecutive_alerts']
        
        logger.info("Simple AI Backend initialized")
        logger.info("✓ Android MQTT topics configured")
    
    def initialize_fcm(self):
        """Initialize Firebase Cloud Messaging"""
        try:
            # Get Firebase credentials path
            firebase_creds = os.getenv('FIREBASE_CREDENTIALS_PATH', 'config/firebase-credentials.json')
            
            if not os.path.exists(firebase_creds):
                logger.warning("⚠️  Firebase credentials not found!")
                logger.warning(f"   Expected: {firebase_creds}")
                logger.warning("   FCM push notifications disabled.")
                return
            
            # Initialize FCM Manager
            self.fcm_manager = FCMManager(firebase_creds)
            
            if not self.fcm_manager.initialized:
                logger.warning("⚠️  FCM initialization failed!")
                return
            
            # Get device token from .env
            self.device_token = os.getenv('ANDROID_FCM_TOKEN')
            
            if self.device_token:
                logger.info(f"✅ FCM device token loaded: {self.device_token[:30]}...")
                
                # Send test notification on startup
                logger.info("📱 Sending test notification...")
                success = self.fcm_manager.send_test_notification(self.device_token)
                
                if success:
                    logger.info("✅ Test notification sent! Check Android device.")
                else:
                    logger.warning("⚠️  Test notification failed. Check token and credentials.")
            else:
                logger.warning("⚠️  No FCM token found in .env")
                logger.warning("   Add: ANDROID_FCM_TOKEN=your_token_here")
                logger.warning("   FCM notifications disabled.")
        
        except Exception as e:
            logger.error(f"❌ FCM initialization error: {e}")
    
    def load_model(self):
        """Load Isolation Forest model"""
        logger.info("Loading AI model...")
        
        try:
            model_path = 'models/isolation_forest.pkl'
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            logger.info(f"✓ Model loaded: Isolation Forest")
            
            scaler_path = 'models/scaler.pkl'
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            logger.info(f"✓ Scaler loaded")
            
            logger.info("✓ AI model ready")
            
        except FileNotFoundError as e:
            logger.error(f"❌ Model files not found: {e}")
            logger.error("Please run 'python src/train_model_simple.py' first!")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise
    
    def detect_anomaly(self, hr, spo2):
        """Use Isolation Forest to detect anomalies"""
        sample = np.array([[hr, spo2]])
        sample_scaled = self.scaler.transform(sample)
        prediction = self.model.predict(sample_scaled)[0]
        score = self.model.score_samples(sample_scaled)[0]
        is_anomaly = (prediction == -1)
        
        anomaly_type = None
        if is_anomaly:
            hr_anomalous = hr < 60 or hr > 100
            spo2_anomalous = spo2 < 95
            
            if hr_anomalous and spo2_anomalous:
                anomaly_type = "HR+SpO2"
            elif hr_anomalous:
                anomaly_type = "HR"
            elif spo2_anomalous:
                anomaly_type = "SpO2"
            else:
                anomaly_type = "Unknown"
        
        return is_anomaly, score, anomaly_type
    
    def check_consecutive_anomalies(self, is_anomaly, anomaly_type):
        """Track consecutive anomalies"""
        if not is_anomaly:
            self.hr_anomaly_count = 0
            self.spo2_anomaly_count = 0
            return False
        
        if anomaly_type in ["HR", "HR+SpO2"]:
            self.hr_anomaly_count += 1
        else:
            self.hr_anomaly_count = 0
        
        if anomaly_type in ["SpO2", "HR+SpO2"]:
            self.spo2_anomaly_count += 1
        else:
            self.spo2_anomaly_count = 0
        
        should_alert = (
            self.hr_anomaly_count >= self.consecutive_alerts or
            self.spo2_anomaly_count >= self.consecutive_alerts or
            anomaly_type == "HR+SpO2"
        )
        
        if should_alert:
            logger.critical(f"🚨 ALERT CONDITION MET!")
            logger.critical(f"   HR anomalies: {self.hr_anomaly_count}")
            logger.critical(f"   SpO2 anomalies: {self.spo2_anomaly_count}")
            
            # Reset
            self.hr_anomaly_count = 0
            self.spo2_anomaly_count = 0
        
        return should_alert
    
    def publish_to_android(self, topic, message, log_message=""):
        """Safely publish to Android app topics via MQTT"""
        if not self.mqtt_client.connected:
            logger.debug(f"Not connected. Skipping MQTT publish to {topic}")
            return False
        
        try:
            success = self.mqtt_client.publish(message, topic=topic)
            if success and log_message:
                logger.info(log_message)
            return success
        except Exception as e:
            logger.debug(f"Error publishing to {topic}: {e}")
            return False
    
    def send_alert(self, hr, spo2, anomaly_type, record_id=None):
        """Send alert via both MQTT and FCM push notification"""
        logger.warning(f"📧 ALERT TRIGGERED:")
        logger.warning(f"   Type: {anomaly_type}")
        logger.warning(f"   HR: {hr} bpm, SpO2: {spo2}%")
        
        # Determine severity
        if anomaly_type == "HR+SpO2":
            severity = "critical"
        elif anomaly_type in ["HR", "SpO2"]:
            severity = "high"
        else:
            severity = "medium"
        
        # 1. Publish to MQTT (for real-time in-app updates)
        message = {
            'timestamp': datetime.now().isoformat(),
            'hr': hr,
            'spo2': spo2,
            'anomaly_type': anomaly_type,
            'severity': severity,
            'record_id': record_id,
            'alert_type': 'anomaly_detected',
            'notification': {
                'title': f'⚠️ Health Alert: {anomaly_type}',
                'body': f'HR: {hr} bpm | SpO2: {spo2}%',
                'importance': 'high'
            }
        }
        
        self.publish_to_android(
            self.android_topics['anomaly_alert'],
            message,
            f"📱 MQTT alert published: {anomaly_type}"
        )
        
        # 2. Send FCM Push Notification (works even when app is closed!)
        if self.fcm_manager and self.device_token:
            try:
                success = self.fcm_manager.send_anomaly_notification(
                    device_token=self.device_token,
                    hr=hr,
                    spo2=spo2,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    record_id=record_id
                )
                
                if success:
                    logger.warning("🔔 FCM push notification sent!")
                else:
                    logger.warning("⚠️  FCM notification failed")
                    
            except Exception as e:
                logger.error(f"Error sending FCM notification: {e}")
        else:
            logger.debug("FCM not available. Skipping push notification.")
    
    def process_message(self, client, userdata, msg):
        """Process MQTT message from simulator"""
        try:
            payload = msg.payload.decode()
            data = json.loads(payload)
            
            timestamp = data.get('timestamp')
            hr = data.get('hr')
            spo2 = data.get('spo2')
            
            # Publish real-time sensor data to Android app
            sensor_msg = {
                'timestamp': timestamp,
                'hr': hr,
                'spo2': spo2,
                'data_type': 'sensor_reading'
            }
            self.publish_to_android(
                self.android_topics['sensor_data'],
                sensor_msg
            )
            
            # AI detection
            is_anomaly, score, anomaly_type = self.detect_anomaly(hr, spo2)
            
            # Log
            if is_anomaly:
                logger.warning(
                    f"🚨 ANOMALY: HR={hr}, SpO2={spo2}% | "
                    f"Type={anomaly_type} | Score={score:.4f}"
                )
            else:
                logger.info(
                    f"✓ Normal: HR={hr}, SpO2={spo2}% | "
                    f"Score={score:.4f}"
                )
            
            # Check consecutive
            should_alert = self.check_consecutive_anomalies(is_anomaly, anomaly_type)
            
            # Save to database
            record = {
                'timestamp': timestamp,
                'hr': hr,
                'spo2': spo2,
                'is_anomaly': 1 if is_anomaly else 0,
                'anomaly_type': anomaly_type,
                'reconstruction_error': float(score)
            }
            
            record_id = self.db.insert_record(record)
            
            if record_id:
                logger.debug(f"  → Saved (ID: {record_id})")
                
                # Send alert if needed
                if should_alert:
                    self.send_alert(hr, spo2, anomaly_type, record_id)
            else:
                logger.error("  → Save failed")
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Start backend"""
        logger.info("=" * 60)
        logger.info("Starting AI Backend with FCM Push Notifications")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Configuration:")
        logger.info(f"  AI Model: Isolation Forest")
        logger.info(f"  Alert After: {self.consecutive_alerts} consecutive anomalies")
        logger.info(f"  MQTT Topics: {list(self.android_topics.values())}")
        logger.info(f"  FCM Enabled: {'✅ Yes' if self.fcm_manager else '❌ No'}")
        logger.info(f"  Device Token: {'✅ Configured' if self.device_token else '❌ Not set'}")
        logger.info("")
        
        # Connect MQTT
        if self.mqtt_client.connect():
            logger.info("✓ Connected to MQTT")
            logger.info(f"✓ Subscribed to: {self.mqtt_client.topic}")
            logger.info("")
            logger.info("📱 System active. Monitoring...")
            logger.info("(Ctrl+C to stop)")
            logger.info("=" * 60)
            logger.info("")
            
            # Give connection a moment to stabilize
            time.sleep(0.5)
            
            # Publish online status
            status_msg = {
                'timestamp': datetime.now().isoformat(),
                'status': 'online',
                'message': 'AI Backend connected and monitoring'
            }
            self.publish_to_android(
                self.android_topics['device_status'],
                status_msg,
                "📱 Backend status published"
            )
            
            # Subscribe
            self.mqtt_client.subscribe(callback=self.process_message)
            
            # Run
            try:
                self.mqtt_client.loop_forever()
            except KeyboardInterrupt:
                logger.info("\n\n" + "=" * 60)
                logger.info("Stopping backend...")
                
                # Publish offline status
                status_msg = {
                    'timestamp': datetime.now().isoformat(),
                    'status': 'offline',
                    'message': 'AI Backend shutting down'
                }
                self.publish_to_android(
                    self.android_topics['device_status'],
                    status_msg
                )
                
                stats = self.db.get_statistics()
                if stats:
                    logger.info("\nSession Statistics:")
                    logger.info(f"  Total: {stats.get('total_records', 0)}")
                    logger.info(f"  Anomalies: {stats.get('total_anomalies', 0)}")
                
                logger.info("=" * 60)
                self.mqtt_client.disconnect()
        else:
            logger.error("Failed to connect to MQTT broker")


def main():
    """Main execution"""
    try:
        backend = SimpleAIBackend()
        backend.start()
    except Exception as e:
        logger.error(f"Backend error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()