"""
Simple Backend for Tomorrow's Demo
Receives MQTT data and stores in database
(No AI model needed for initial demo)
Member B: Backend Logic
"""

import json
import logging
import sys
import time

# Add parent directory to path
sys.path.append('.')

from src.mqtt_client import MQTTClient
from src.db_manager import DatabaseManager
from config_loader import get_config

def to_float(value):
    """Convert Decimal/str/int to float safely."""
    try:
        if value is None:
            return None
        return float(value)
    except:
        return None


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthMonitorBackend:
    def __init__(self):
        """Initialize backend"""
        self.config = get_config()
        self.db = DatabaseManager()
        config = get_config()
        self.mqtt_client = MQTTClient(client_id=config.get('MQTT_CLIENT_ID_BACKEND'))
        
        # Normal ranges (for simple rule-based detection)
        sim_config = self.config.get_section('simulation')
        self.hr_normal = sim_config['hr_normal_range']
        self.spo2_normal = sim_config['spo2_normal_range']
        
        logger.info("Health Monitor Backend initialized")
        logger.info(f"  HR Normal Range: {self.hr_normal}")
        logger.info(f"  SpO2 Normal Range: {self.spo2_normal}")
    
    def is_anomalous(self, hr, spo2):
        """
        Simple rule-based anomaly detection
        (Will be replaced with AI model later)
        """
        hr_anomaly = hr < self.hr_normal[0] or hr > self.hr_normal[1]
        spo2_anomaly = spo2 < self.spo2_normal[0]
        
        is_anomaly = hr_anomaly or spo2_anomaly
        
        # Determine anomaly type
        if hr_anomaly and spo2_anomaly:
            anomaly_type = "HR+SpO2"
        elif hr_anomaly:
            anomaly_type = "HR"
        elif spo2_anomaly:
            anomaly_type = "SpO2"
        else:
            anomaly_type = None
        
        return is_anomaly, anomaly_type
    
    def process_message(self, client, userdata, msg):
        """
        Process incoming MQTT message
        """
        try:
            # Parse message
            payload = msg.payload.decode()
            data = json.loads(payload)
            
            # Extract values
            timestamp = data.get('timestamp')
            hr = data.get('hr')
            spo2 = data.get('spo2')
            
            # Check for anomalies
            is_anomaly, anomaly_type = self.is_anomalous(hr, spo2)
            
            # Log
            if is_anomaly:
                logger.warning(f"🚨 ANOMALY DETECTED: HR={hr}, SpO2={spo2}% | Type: {anomaly_type}")
            else:
                logger.info(f"✓ Normal reading: HR={hr}, SpO2={spo2}%")
            
            # Prepare database record
            record = {
                'timestamp': timestamp,
                'hr': to_float(hr),
                'spo2': to_float(spo2),
                'is_anomaly': 1 if is_anomaly else 0,
                'anomaly_type': anomaly_type,
                'reconstruction_error': None  # No AI model yet
            }
            
            # Save to database
            record_id = self.db.insert_record(record)
            
            if record_id:
                logger.debug(f"  → Saved to database (ID: {record_id})")
            else:
                logger.error("  → Failed to save to database")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Start the backend service"""
        logger.info("=" * 60)
        logger.info("Starting Health Monitor Backend")
        logger.info("=" * 60)
        logger.info("")
        
        # Connect to MQTT. Start the background network loop (loop_start)
        # and use that to receive messages. Keep the main thread alive
        # with a simple sleep loop so callbacks run in the background.
        if not self.mqtt_client.connect():
            logger.error("Failed to connect to MQTT broker!")
            return

        logger.info("✓ Connected to MQTT broker")
        logger.info(f"✓ Subscribed to: {self.mqtt_client.topic}")
        logger.info("")
        logger.info("Waiting for sensor data... (Ctrl+C to stop)")
        logger.info("=" * 60)
        logger.info("")

        # Subscribe with custom callback
        self.mqtt_client.subscribe(callback=self.process_message)

        # Keep running while background network loop handles MQTT I/O
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n\n" + "=" * 60)
            logger.info("Stopping backend...")
            logger.info("=" * 60)
            self.mqtt_client.disconnect()
        
    


def main():
    """Main execution"""
    try:
        backend = HealthMonitorBackend()
        backend.start()
    except Exception as e:
        logger.error(f"Backend error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()