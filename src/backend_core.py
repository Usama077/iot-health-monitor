"""
Backend with Simple AI (Isolation Forest)
No TensorFlow required - uses only scikit-learn
"""

import time
import json
import logging
import sys
import pickle
import numpy as np

# Add parent directory to path
sys.path.append('.')

from src.mqtt_client import MQTTClient
from src.db_manager import DatabaseManager
from config_loader import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleAIBackend:
    def __init__(self):
        """Initialize backend with Isolation Forest model"""
        self.config = get_config()
        self.db = DatabaseManager()
        self.mqtt_client = MQTTClient()
        
        # Load AI model
        self.model = None
        self.scaler = None
        self.load_model()
        
        # Alert tracking
        self.hr_anomaly_count = 0
        self.spo2_anomaly_count = 0
        
        # Configuration
        ai_config = self.config.get_section('ai_model')
        self.consecutive_alerts = ai_config['consecutive_alerts']
        
        logger.info("Simple AI Backend initialized")
    
    def load_model(self):
        """Load Isolation Forest model"""
        logger.info("Loading AI model...")
        
        try:
            # Load model
            model_path = 'models/isolation_forest.pkl'
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            logger.info(f"✓ Model loaded: Isolation Forest")
            
            # Load scaler
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
        """
        Use Isolation Forest to detect anomalies
        
        Args:
            hr (int): Heart rate
            spo2 (int): SpO2 level
        
        Returns:
            tuple: (is_anomaly, anomaly_score, anomaly_type)
        """
        # Prepare input
        sample = np.array([[hr, spo2]])
        
        # Scale
        sample_scaled = self.scaler.transform(sample)
        
        # Predict (-1 = anomaly, 1 = normal)
        prediction = self.model.predict(sample_scaled)[0]
        
        # Get anomaly score (lower = more anomalous)
        score = self.model.score_samples(sample_scaled)[0]
        
        is_anomaly = (prediction == -1)
        
        # Determine anomaly type
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
        """
        Track consecutive anomalies
        
        Args:
            is_anomaly (bool): Whether current reading is anomalous
            anomaly_type (str): Type of anomaly
        
        Returns:
            bool: Whether to send alert
        """
        if not is_anomaly:
            self.hr_anomaly_count = 0
            self.spo2_anomaly_count = 0
            return False
        
        # Track by type
        if anomaly_type in ["HR", "HR+SpO2"]:
            self.hr_anomaly_count += 1
        else:
            self.hr_anomaly_count = 0
        
        if anomaly_type in ["SpO2", "HR+SpO2"]:
            self.spo2_anomaly_count += 1
        else:
            self.spo2_anomaly_count = 0
        
        # Check alert threshold
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
    
    def send_alert(self, hr, spo2, anomaly_type):
        """Send alert"""
        logger.warning(f"📧 EMAIL ALERT WOULD BE SENT:")
        logger.warning(f"   Type: {anomaly_type}")
        logger.warning(f"   HR: {hr} bpm, SpO2: {spo2}%")
    
    def process_message(self, client, userdata, msg):
        """Process MQTT message"""
        try:
            # Parse
            payload = msg.payload.decode()
            data = json.loads(payload)
            
            timestamp = data.get('timestamp')
            hr = data.get('hr')
            spo2 = data.get('spo2')
            
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
            
            if should_alert:
                self.send_alert(hr, spo2, anomaly_type)
            
            # Save to database
            record = {
                'timestamp': timestamp,
                'hr': hr,
                'spo2': spo2,
                'is_anomaly': 1 if is_anomaly else 0,
                'anomaly_type': anomaly_type,
                'reconstruction_error': float(score)  # Use anomaly score
            }
            
            record_id = self.db.insert_record(record)
            
            if record_id:
                logger.debug(f"  → Saved (ID: {record_id})")
            else:
                logger.error("  → Save failed")
        
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Start backend with automatic reconnection"""
        logger.info("=" * 60)
        logger.info("Starting Simple AI Backend")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Configuration:")
        logger.info(f"  AI Model: Isolation Forest")
        logger.info(f"  Alert After: {self.consecutive_alerts} consecutive anomalies")
        logger.info("")
        
        # Connect MQTT with retry
        max_connection_attempts = 5
        attempt = 0
        
        while attempt < max_connection_attempts:
            if self.mqtt_client.connect():
                logger.info("✓ Connected to MQTT")
                logger.info(f"✓ Subscribed to: {self.mqtt_client.topic}")
                logger.info("")
                logger.info("AI system active. Monitoring...")
                logger.info("(Ctrl+C to stop)")
                logger.info("=" * 60)
                logger.info("")
                
                # Subscribe
                self.mqtt_client.subscribe(callback=self.process_message)
                
                # Run with auto-reconnect
                try:
                    self.mqtt_client.loop_forever()
                except KeyboardInterrupt:
                    logger.info("\n\n" + "=" * 60)
                    logger.info("Stopping backend...")
                    
                    stats = self.db.get_statistics()
                    if stats:
                        logger.info("\nSession Statistics:")
                        logger.info(f"  Total: {stats.get('total_records', 0)}")
                        logger.info(f"  Anomalies: {stats.get('total_anomalies', 0)}")
                    
                    logger.info("=" * 60)
                    self.mqtt_client.disconnect()
                    break
                except Exception as e:
                    logger.error(f"Connection lost: {e}")
                    logger.info("Attempting to reconnect...")
                    attempt += 1
                    time.sleep(5)
            else:
                logger.error(f"Connection attempt {attempt + 1} failed")
                attempt += 1
                if attempt < max_connection_attempts:
                    logger.info(f"Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    logger.error("Max connection attempts reached. Exiting.")
                    break


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