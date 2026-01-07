"""
MQTT Connection Tester
Quick diagnostic tool to check MQTT broker connectivity
"""

import paho.mqtt.client as mqtt
import time
import json
from datetime import datetime

print("=" * 60)
print("MQTT Connection Tester")
print("=" * 60)
print()

# Test configuration
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "test/iot_health_monitor"
CLIENT_ID = "test_client"

print(f"Testing connection to: {BROKER}:{PORT}")
print(f"Topic: {TOPIC}")
print()

# Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✓ Connected successfully!")
        print(f"  Return code: {rc}")
        print(f"  Flags: {flags}")
    else:
        print(f"✗ Connection failed with code: {rc}")
        errors = {
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized"
        }
        print(f"  Error: {errors.get(rc, 'Unknown error')}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"⚠ Unexpected disconnect (code: {rc})")
    else:
        print("✓ Disconnected cleanly")

def on_publish(client, userdata, mid):
    print(f"✓ Message published (mid: {mid})")

def on_message(client, userdata, msg):
    print(f"📨 Message received:")
    print(f"   Topic: {msg.topic}")
    print(f"   Payload: {msg.payload.decode()}")

def on_subscribe(client, userdata, mid, granted_qos):
    print(f"✓ Subscribed (QoS: {granted_qos})")

# Create client
print("Creating MQTT client...")
client = mqtt.Client(client_id=CLIENT_ID)

# Set callbacks
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish
client.on_message = on_message
client.on_subscribe = on_subscribe

# Enable logging
client.enable_logger()

try:
    print("\n1. Connecting to broker...")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    
    # Wait for connection
    time.sleep(3)
    
    if client.is_connected():
        print("\n2. Subscribing to topic...")
        client.subscribe(TOPIC, qos=1)
        time.sleep(1)
        
        print("\n3. Publishing test message...")
        test_msg = {
            "timestamp": datetime.now().isoformat(),
            "hr": 75,
            "spo2": 98,
            "test": True
        }
        
        result = client.publish(TOPIC, json.dumps(test_msg), qos=1)
        result.wait_for_publish()
        
        print("\n4. Waiting for message (5 seconds)...")
        time.sleep(5)
        
        print("\n" + "=" * 60)
        print("✅ Test Complete - MQTT is working!")
        print("=" * 60)
    else:
        print("\n❌ Failed to connect")
        print("\nTroubleshooting:")
        print("1. Check internet connection")
        print("2. Try a different broker:")
        print("   - test.mosquitto.org")
        print("   - broker.emqx.io")
        print("3. Check firewall settings")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    print("\nCleaning up...")
    client.loop_stop()
    client.disconnect()
    print("Done.")