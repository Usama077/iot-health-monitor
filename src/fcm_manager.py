"""
Firebase Cloud Messaging Manager
Sends push notifications to Android app
"""

import logging
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, messaging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FCMManager:
    def __init__(self, credentials_path):
        """
        Initialize Firebase Admin SDK
        
        Args:
            credentials_path (str): Path to Firebase service account JSON
        """
        self.credentials_path = credentials_path
        self.app = None
        self.initialized = False
        
        try:
            # Initialize Firebase Admin
            cred = credentials.Certificate(self.credentials_path)
            self.app = firebase_admin.initialize_app(cred)
            self.initialized = True
            logger.info("✅ Firebase Admin SDK initialized")
            logger.info(f"   Project: {cred.project_id}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase: {e}")
            self.initialized = False
    
    def send_anomaly_notification(self, device_token, hr, spo2, anomaly_type, severity, record_id=None):
        """
        Send push notification for health anomaly
        
        Args:
            device_token (str): FCM device registration token
            hr (int): Heart rate
            spo2 (int): SpO2 level
            anomaly_type (str): Type of anomaly (HR, SpO2, HR+SpO2)
            severity (str): Severity level (critical, high, medium)
            record_id (int, optional): Database record ID
        
        Returns:
            bool: True if notification sent successfully
        """
        if not self.initialized:
            logger.error("FCM not initialized. Cannot send notification.")
            return False
        
        if not device_token:
            logger.warning("No device token provided. Cannot send notification.")
            return False
        
        try:
            # Determine emoji and color based on severity
            if severity == "critical":
                emoji = "🚨"
                color = "#FF0000"
                priority = "high"
            elif severity == "high":
                emoji = "⚠️"
                color = "#FFA500"
                priority = "high"
            else:
                emoji = "⚡"
                color = "#FFA500"
                priority = "default"
            
            # Create notification title and body
            title = f"{emoji} Health Alert: {anomaly_type}"
            body = f"HR: {hr} bpm | SpO2: {spo2}%"
            
            # Build notification message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data={
                    'type': 'anomaly_alert',
                    'anomaly_type': anomaly_type,
                    'hr': str(hr),
                    'spo2': str(spo2),
                    'severity': severity,
                    'timestamp': datetime.now().isoformat(),
                    'record_id': str(record_id) if record_id else '',
                },
                android=messaging.AndroidConfig(
                    priority=priority,
                    notification=messaging.AndroidNotification(
                        icon='ic_health_alert',
                        color=color,
                        sound='default',
                        channel_id='health_alerts',
                    ),
                ),
                token=device_token,
            )
            
            # Send notification
            response = messaging.send(message)
            
            logger.warning(f"🔔 FCM Notification sent: {title}")
            logger.warning(f"   HR: {hr} bpm, SpO2: {spo2}%")
            logger.warning(f"   Severity: {severity}")
            logger.warning(f"   Message ID: {response}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send FCM notification: {e}")
            return False
    
    def send_status_notification(self, device_token, status, message_text):
        """
        Send backend status notification
        
        Args:
            device_token (str): FCM device registration token
            status (str): Status type (online, offline, error)
            message_text (str): Status message
        
        Returns:
            bool: True if notification sent successfully
        """
        if not self.initialized or not device_token:
            return False
        
        try:
            title = f"Backend {status.title()}"
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=message_text,
                ),
                data={
                    'type': 'status_update',
                    'status': status,
                    'timestamp': datetime.now().isoformat(),
                },
                android=messaging.AndroidConfig(
                    priority='default',
                    notification=messaging.AndroidNotification(
                        channel_id='backend_status',
                    ),
                ),
                token=device_token,
            )
            
            response = messaging.send(message)
            logger.info(f"📱 Status notification sent: {status}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send status notification: {e}")
            return False
    
    def send_test_notification(self, device_token):
        """
        Send test notification to verify FCM setup
        
        Args:
            device_token (str): FCM device registration token
        
        Returns:
            bool: True if test notification sent successfully
        """
        if not self.initialized:
            logger.error("FCM not initialized")
            return False
        
        if not device_token:
            logger.error("No device token provided")
            return False
        
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="🧪 Test Notification",
                    body="FCM is working! Health monitoring is active.",
                ),
                data={
                    'type': 'test',
                    'timestamp': datetime.now().isoformat(),
                },
                token=device_token,
            )
            
            response = messaging.send(message)
            logger.info(f"✅ Test notification sent successfully!")
            logger.info(f"   Message ID: {response}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send test notification: {e}")
            logger.error(f"   Token: {device_token[:20]}...")
            return False


# Utility function for easy import
def get_fcm_manager(credentials_path):
    """
    Factory function to create FCM Manager
    
    Args:
        credentials_path (str): Path to Firebase credentials JSON
    
    Returns:
        FCMManager: Initialized FCM manager instance
    """
    return FCMManager(credentials_path)