"""
MQTT Client Utility Module
Handles connection setup and publishing/subscribing logic
Member A: IoT Infrastructure
"""

import random
import string
import paho.mqtt.client as mqtt
import json
import logging
import time
from config_loader import get_config


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class   MQTTClient:
   # At the top, add import
# Replace __init__ method:
    def __init__(self, client_id=None):
        """
        Initialize MQTT client with configuration
        """
        config = get_config()
        mqtt_config = config.get_section('mqtt')
        
        self.broker = mqtt_config['broker']
        # Ensure port is an integer
        port = mqtt_config['port']
        self.port = int(port) if isinstance(port, str) else port
        self.topic = mqtt_config['topic']
        
        if client_id is None:
            client_id = 'client_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.client_id = client_id
        
        self.client = mqtt.Client(client_id=self.client_id)
        self.connected = False
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        logger.info(f"MQTT Client initialized: {self.client_id}")
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"✓ Connected to MQTT Broker: {self.broker}:{self.port}")
        else:
            logger.error(f"✗ Connection failed with code: {rc}")
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            logger.error(f"   Reason: {error_messages.get(rc, 'Unknown error')}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠ Unexpected disconnection (code: {rc})")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Default message callback - can be overridden"""
        try:
            payload = msg.payload.decode()
            logger.info(f"📨 Message received on {msg.topic}")
            logger.debug(f"   Payload: {payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def connect(self, timeout=10, start_loop=True):
        """
        Connect to MQTT broker
        
        Args:
            timeout (int): Connection timeout in seconds
            start_loop (bool): If True, start background network loop (loop_start). If False, caller will run loop.
        
        Returns:
            bool: True if connected successfully
        """
        try:
            logger.info(f"Connecting to {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, keepalive=60)
            # Start network loop in background only if requested. For long-running
            # subscriber processes that call `loop_forever()` themselves, pass
            # start_loop=False to avoid mixing loop modes.
            if start_loop:
                self.client.loop_start()
            
            # Wait for connection
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.connected:
                return True
            else:
                logger.error("Connection timeout")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")
    
    def publish(self, message, topic=None):
        """
        Publish message to MQTT topic
        
        Args:
            message (dict or str): Message to publish
            topic (str, optional): Topic to publish to. Uses default if None.
        
        Returns:
            bool: True if published successfully
        """
        if not self.connected:
            logger.error("Not connected to broker! Call connect() first.")
            return False
        
        publish_topic = topic or self.topic
        
        # Convert dict to JSON string
        if isinstance(message, dict):
            message = json.dumps(message)
        
        try:
            result = self.client.publish(publish_topic, message, qos=1)
            
            # Wait for message to be sent
            result.wait_for_publish()
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📤 Published to {publish_topic}")
                return True
            else:
                logger.error(f"Publish failed with code: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False
    
    def subscribe(self, topic=None, callback=None):
        """
        Subscribe to MQTT topic
        
        Args:
            topic (str, optional): Topic to subscribe to. Uses default if None.
            callback (function, optional): Custom message handler
        
        Returns:
            bool: True if subscribed successfully
        """
        if not self.connected:
            logger.error("Not connected to broker! Call connect() first.")
            return False
        
        subscribe_topic = topic or self.topic
        
        # Set custom callback if provided
        if callback:
            self.client.on_message = callback
        
        try:
            result = self.client.subscribe(subscribe_topic, qos=1)
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"✓ Subscribed to: {subscribe_topic}")
                return True
            else:
                logger.error(f"Subscribe failed with code: {result[0]}")
                return False
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return False
    
    def loop_forever(self):
        logger.info("Starting MQTT loop...")
        try:
            # Use paho-mqtt's built-in blocking loop which handles reconnection
            # and socket polling. Callers should ensure they did not start the
            # background loop (i.e., connect(start_loop=False)).
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Stopping MQTT client...")
            self.disconnect()



# Test functions
def test_publish():
    """Test publishing messages"""
    logger.info("=" * 60)
    logger.info("Testing MQTT Publishing")
    logger.info("=" * 60)
    
    client = MQTTClient()
    
    if client.connect():
        # Send test message
        test_message = {
            "timestamp": "2025-12-09T10:30:00",
            "hr": 75,
            "spo2": 98,
            "test": True
        }
        
        logger.info("Sending test message...")
        success = client.publish(test_message)
        
        if success:
            logger.info("✅ Test message sent successfully!")
        else:
            logger.error("❌ Failed to send test message")
        
        time.sleep(2)
        client.disconnect()
    else:
        logger.error("❌ Connection failed")


def test_subscribe():
    """Test subscribing to messages"""
    logger.info("=" * 60)
    logger.info("Testing MQTT Subscription")
    logger.info("=" * 60)
    logger.info("Listening for messages... (Ctrl+C to stop)")
    
    def message_handler(client, userdata, msg):
        """Custom message handler"""
        try:
            payload = msg.payload.decode()
            data = json.loads(payload)
            logger.info(f"📨 Received: HR={data.get('hr')}, SpO2={data.get('spo2')}")
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
    
    client = MQTTClient()
    
    if client.connect():
        client.subscribe(callback=message_handler)
        client.loop_forever()
    else:
        logger.error("❌ Connection failed")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "pub":
            test_publish()
        elif sys.argv[1] == "sub":
            test_subscribe()
        else:
            print("Usage:")
            print("  python mqtt_client.py pub  # Test publishing")
            print("  python mqtt_client.py sub  # Test subscribing")
    else:
        print("Testing MQTT connection...")
        test_publish()