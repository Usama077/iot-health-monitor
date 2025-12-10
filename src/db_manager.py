"""
MySQL Database Manager Module
Handles MySQL database operations for health monitoring data
Member A: IoT Infrastructure
"""

import mysql.connector
from mysql.connector import Error
from config_loader import get_config
import json
import logging
from datetime import datetime
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        """
        Initialize MySQL database manager
        """
        config = get_config()
        self.db_config = config.get_section('database')
        self.connection_pool = None
        
        # Test connection and create table
        self.test_connection()
        self.create_table()
        
        logger.info(f"✓ MySQL Database initialized: {self.db_config['database']}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        connection = None
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            yield connection
            connection.commit()
        except Error as e:
            if connection:
                connection.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    def test_connection(self):
        """Test MySQL connection"""
        try:
            with self.get_connection() as conn:
                if conn.is_connected():
                    db_info = conn.get_server_info()
                    logger.info(f"✓ Connected to MySQL Server version {db_info}")
                    return True
        except Error as e:
            logger.error(f"✗ Connection failed: {e}")
            logger.error("Please check:")
            logger.error("  1. MySQL is running: sudo systemctl status mysql")
            logger.error("  2. Credentials in config.json are correct")
            logger.error("  3. Database 'health_monitor' exists")
            raise
    
    def create_table(self):
        """Create health_data table if it doesn't exist"""
        create_query = """
        CREATE TABLE IF NOT EXISTS health_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            hr INT NOT NULL,
            spo2 INT NOT NULL,
            is_anomaly TINYINT(1) NOT NULL DEFAULT 0,
            anomaly_type VARCHAR(50),
            reconstruction_error FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_timestamp (timestamp DESC),
            INDEX idx_anomaly (is_anomaly)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_query)
                logger.info("✓ Database table created/verified")
        except Error as e:
            logger.error(f"Failed to create table: {e}")
            raise
    
    def insert_record(self, data):
        """
        Insert a single health record
        
        Args:
            data (dict): Record containing:
                - timestamp: ISO format timestamp or datetime object
                - hr: Heart rate value
                - spo2: SpO2 value
                - is_anomaly: Boolean or 0/1
                - anomaly_type: Type of anomaly (optional)
                - reconstruction_error: AI model error (optional)
        
        Returns:
            int: ID of inserted record, or None if failed
        """
        insert_query = """
        INSERT INTO health_data 
        (timestamp, hr, spo2, is_anomaly, anomaly_type, reconstruction_error)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        try:
            # Convert ISO string to datetime if needed
            timestamp = data.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(insert_query, (
                    timestamp,
                    data.get('hr'),
                    data.get('spo2'),
                    int(data.get('is_anomaly', 0)),
                    data.get('anomaly_type'),
                    data.get('reconstruction_error')
                ))
                return cursor.lastrowid
        except Error as e:
            logger.error(f"Failed to insert record: {e}")
            return None
    
    def get_latest_records(self, limit=50):
        """
        Retrieve the most recent records
        
        Args:
            limit (int): Number of records to retrieve
        
        Returns:
            list: List of dictionaries containing record data
        """
        query = """
        SELECT id, timestamp, hr, spo2, is_anomaly, 
               anomaly_type, reconstruction_error, created_at
        FROM health_data 
        ORDER BY timestamp DESC 
        LIMIT %s
        """
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
                
                # Convert datetime to string for JSON serialization
                for row in rows:
                    if isinstance(row['timestamp'], datetime):
                        row['timestamp'] = row['timestamp'].isoformat()
                    if isinstance(row['created_at'], datetime):
                        row['created_at'] = row['created_at'].isoformat()
                
                return rows
        except Error as e:
            logger.error(f"Failed to fetch records: {e}")
            return []
    
    def get_records_by_time_range(self, start_time, end_time):
        """
        Get records within a time range
        
        Args:
            start_time (str): Start timestamp (ISO format)
            end_time (str): End timestamp (ISO format)
        
        Returns:
            list: Records within the time range
        """
        query = """
        SELECT id, timestamp, hr, spo2, is_anomaly, 
               anomaly_type, reconstruction_error
        FROM health_data 
        WHERE timestamp BETWEEN %s AND %s
        ORDER BY timestamp ASC
        """
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (start_time, end_time))
                rows = cursor.fetchall()
                
                for row in rows:
                    if isinstance(row['timestamp'], datetime):
                        row['timestamp'] = row['timestamp'].isoformat()
                
                return rows
        except Error as e:
            logger.error(f"Failed to fetch time range: {e}")
            return []
    
    def get_anomaly_count(self, hours=24):
        """
        Get count of anomalies in the last N hours
        
        Args:
            hours (int): Number of hours to look back
        
        Returns:
            int: Number of anomalies detected
        """
        query = """
        SELECT COUNT(*) as count 
        FROM health_data 
        WHERE is_anomaly = 1 
        AND timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR)
        """
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (hours,))
                result = cursor.fetchone()
                return result['count'] if result else 0
        except Error as e:
            logger.error(f"Failed to get anomaly count: {e}")
            return 0
    
    def clear_old_records(self, days=30):
        """
        Delete records older than N days to save space
        
        Args:
            days (int): Keep records from the last N days
        
        Returns:
            int: Number of records deleted
        """
        query = """
        DELETE FROM health_data 
        WHERE timestamp < DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (days,))
                deleted = cursor.rowcount
                logger.info(f"Deleted {deleted} old records")
                return deleted
        except Error as e:
            logger.error(f"Failed to clear old records: {e}")
            return 0
    
    def get_statistics(self):
        """
        Get overall database statistics
        
        Returns:
            dict: Statistics including total records, anomalies, etc.
        """
        query = """
        SELECT 
            COUNT(*) as total_records,
            SUM(is_anomaly) as total_anomalies,
            AVG(hr) as avg_hr,
            AVG(spo2) as avg_spo2,
            MIN(timestamp) as first_record,
            MAX(timestamp) as last_record
        FROM health_data
        """
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query)
                result = cursor.fetchone()
                
                if result and result['first_record']:
                    result['first_record'] = result['first_record'].isoformat()
                if result and result['last_record']:
                    result['last_record'] = result['last_record'].isoformat()
                
                return result if result else {}
        except Error as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def get_recent_anomalies(self, limit=10):
        """
        Get recent anomaly records
        
        Args:
            limit (int): Number of anomalies to retrieve
        
        Returns:
            list: Recent anomaly records
        """
        query = """
        SELECT timestamp, hr, spo2, anomaly_type, reconstruction_error
        FROM health_data 
        WHERE is_anomaly = 1
        ORDER BY timestamp DESC 
        LIMIT %s
        """
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
                
                for row in rows:
                    if isinstance(row['timestamp'], datetime):
                        row['timestamp'] = row['timestamp'].isoformat()
                
                return rows
        except Error as e:
            logger.error(f"Failed to fetch anomalies: {e}")
            return []


# Testing function
def test_database():
    """Test database operations"""
    logger.info("=" * 60)
    logger.info("Testing MySQL Database Manager")
    logger.info("=" * 60)
    
    try:
        db = DatabaseManager()
        
        # Test insert
        test_record = {
            'timestamp': datetime.now(),
            'hr': 75,
            'spo2': 98,
            'is_anomaly': 0,
            'anomaly_type': None,
            'reconstruction_error': 0.02
        }
        
        record_id = db.insert_record(test_record)
        logger.info(f"✓ Inserted test record ID: {record_id}")
        
        # Test retrieval
        records = db.get_latest_records(limit=5)
        logger.info(f"✓ Retrieved {len(records)} records")
        
        # Test statistics
        stats = db.get_statistics()
        logger.info(f"✓ Database stats:")
        logger.info(f"   Total records: {stats.get('total_records', 0)}")
        logger.info(f"   Total anomalies: {stats.get('total_anomalies', 0)}")
        logger.info(f"   Avg HR: {stats.get('avg_hr', 0):.1f}")
        logger.info(f"   Avg SpO2: {stats.get('avg_spo2', 0):.1f}")
        
        logger.info("\n✅ All tests passed!")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")


if __name__ == "__main__":
    test_database()