"""
IoT Sensor Simulator
Simulates real-time health monitoring sensors sending data via MQTT
Member A: IoT Infrastructure
"""
import json  
import time
import random
from datetime import datetime
import logging
import sys

# Add parent directory to path
sys.path.append('.')

from src.mqtt_client import MQTTClient
import paho.mqtt.client as mqtt
from config_loader import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthSensorSimulator:
    def __init__(self):
        """Initialize sensor simulator"""
        self.config = get_config()
        sim_config = self.config.get_section('simulation')
        
        # Normal ranges
        self.hr_range = sim_config['hr_normal_range']
        self.spo2_range = sim_config['spo2_normal_range']
        self.anomaly_prob = sim_config['anomaly_probability']
        self.send_interval = sim_config['send_interval']
        
        # MQTT client
        self.mqtt_client = mqtt.Client(client_id=self.config.get('MQTT_CLIENT_ID_SENSOR'))        
        # Anomaly tracking (for demo purposes)
        self.consecutive_hr_anomalies = 0
        self.consecutive_spo2_anomalies = 0
        self.readings_count = 0
        
        logger.info("Health Sensor Simulator initialized")
        logger.info(f"  HR Normal Range: {self.hr_range}")
        logger.info(f"  SpO2 Normal Range: {self.spo2_range}")
        logger.info(f"  Anomaly Probability: {self.anomaly_prob * 100}%")
        logger.info(f"  Send Interval: {self.send_interval} seconds")
    
    def generate_normal_reading(self):
        """Generate normal health readings"""
        hr = random.randint(self.hr_range[0], self.hr_range[1])
        spo2 = random.randint(self.spo2_range[0], self.spo2_range[1])
        return hr, spo2
    
    def generate_anomalous_reading(self):
        """Generate anomalous health readings"""
        anomaly_type = random.choice(['hr', 'spo2', 'both'])
        
        if anomaly_type == 'hr':
            # Abnormal heart rate (too high or too low)
            hr = random.choice([
                random.randint(110, 150),  # Tachycardia
                random.randint(40, 55)     # Bradycardia
            ])
            spo2 = random.randint(self.spo2_range[0], self.spo2_range[1])
            
        elif anomaly_type == 'spo2':
            # Low blood oxygen
            hr = random.randint(self.hr_range[0], self.hr_range[1])
            spo2 = random.randint(85, 92)  # Hypoxemia
            
        else:  # both
            # Both abnormal
            hr = random.randint(110, 150)
            spo2 = random.randint(85, 92)
        
        return hr, spo2
    
    def should_generate_anomaly(self):
        """
        Decide whether to generate an anomaly
        Ensures demo patterns occur (3 consecutive anomalies)
        """
        # Every 30 readings, force a pattern for demo
        if self.readings_count > 0 and self.readings_count % 30 == 0:
            return True
        
        # Otherwise, random probability
        return random.random() < self.anomaly_prob
    
    def create_reading(self):
        """Create a single sensor reading"""
        timestamp = datetime.now().isoformat()
        
        # Decide normal vs anomalous
        if self.should_generate_anomaly():
            hr, spo2 = self.generate_anomalous_reading()
            logger.warning(f"⚠️  ANOMALY: HR={hr}, SpO2={spo2}%")
        else:
            hr, spo2 = self.generate_normal_reading()
            logger.info(f"✓ Normal: HR={hr}, SpO2={spo2}%")
        
        # Create message
        message = {
            "timestamp": timestamp,
            "hr": hr,
            "spo2": spo2,
            "device_id": "sensor_001",
            "reading_number": self.readings_count
        }
        
        self.readings_count += 1
        return message
    
    def start(self):
        """Start the sensor simulation"""
        logger.info("=" * 60)
        logger.info("Starting IoT Health Sensor Simulation")
        logger.info("=" * 60)
        logger.info("")

        # Get broker details from config
        broker = self.config.get('mqtt', 'broker')
        port = self.config.get('mqtt', 'port')
        topic = self.config.get('mqtt', 'topic')

        # Connect to MQTT broker
        try:
            self.mqtt_client.connect(host=broker, port=port, keepalive=60)
            self.mqtt_client.loop_start()  # Start background thread for network events
            logger.info(f"✓ Connected to MQTT broker: {broker}:{port}")
            logger.info(f"✓ Publishing to topic: {topic}")
            logger.info("")
            logger.info("Generating sensor readings... (Ctrl+C to stop)")
            logger.info("=" * 60)
            logger.info("")

        except Exception as e:
            logger.error("Failed to connect to MQTT broker!")
            logger.error(f"Error: {e}")
            logger.error("Please check:")
            logger.error("  1. Internet connection")
            logger.error(f"  2. Broker {broker}:{port} is accessible")
            return

        try:
            while True:
                # Create and send reading
                reading = self.create_reading()
                payload = json.dumps(reading)  # Make sure it's a JSON string
                result = self.mqtt_client.publish(topic, payload)

                if result.rc != 0:  # 0 = MQTT_ERR_SUCCESS
                    logger.error(f"Failed to publish reading (rc={result.rc})")
                else:
                    logger.info(f"Published: HR={reading['hr']}, SpO2={reading['spo2']}")
                # Wait before next reading
                time.sleep(self.send_interval)

        except KeyboardInterrupt:
            logger.info("\n\n" + "=" * 60)
            logger.info("Stopping sensor simulation...")
            logger.info(f"Total readings sent: {self.readings_count}")
            logger.info("=" * 60)

        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("Disconnected from MQTT broker")

def main():
    """Main execution"""
    try:
        simulator = HealthSensorSimulator()
        simulator.start()
    except Exception as e:
        logger.error(f"Simulator error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()