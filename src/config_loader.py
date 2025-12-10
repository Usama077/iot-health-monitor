"""
Configuration Loader with Environment Variables Support
Loads config.json and replaces placeholders with .env values
"""

import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigLoader:
    def __init__(self, config_path='config.json', env_path='.env'):
        """
        Initialize config loader
        
        Args:
            config_path (str): Path to config.json
            env_path (str): Path to .env file
        """
        self.config_path = config_path
        self.env_path = env_path
        self.config = None
        
        # Load environment variables
        self._load_env()
        
        # Load and process config
        self.config = self._load_config()
    
    def _load_env(self):
        """Load environment variables from .env file"""
        if os.path.exists(self.env_path):
            load_dotenv(self.env_path)
            logger.info(f"✓ Environment variables loaded from {self.env_path}")
        else:
            logger.warning(f"⚠️  {self.env_path} not found!")
            logger.warning("   Create it using .env.example as a template")
            logger.warning("   cp .env.example .env")
    
    def _load_config(self):
        """Load config.json and replace environment variable placeholders"""
        try:
            with open(self.config_path, 'r') as f:
                config_str = f.read()
            
            # Replace ${VAR_NAME} with environment variable values
            def replace_env_var(match):
                var_name = match.group(1)
                value = os.getenv(var_name)
                
                if value is None:
                    logger.warning(f"⚠️  Environment variable '{var_name}' not set!")
                    return match.group(0)  # Keep placeholder if not found
                
                return value
            
            # Replace all ${VAR_NAME} patterns
            config_str = re.sub(r'\$\{([^}]+)\}', replace_env_var, config_str)
            
            # Parse JSON
            config = json.loads(config_str)
            
            # Convert port values to integers where needed
            if 'mqtt' in config and 'port' in config['mqtt']:
                if isinstance(config['mqtt']['port'], str):
                    config['mqtt']['port'] = int(config['mqtt']['port'])
            
            if 'database' in config and 'port' in config['database']:
                if isinstance(config['database']['port'], str):
                    config['database']['port'] = int(config['database']['port'])
            
            logger.info(f"✓ Configuration loaded from {self.config_path}")
            return config
            
        except FileNotFoundError:
            logger.error(f"❌ Config file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            raise
    
    def get(self, *keys, default=None):
        """
        Get nested config value
        
        Args:
            *keys: Sequence of keys to navigate (e.g., 'database', 'host')
            default: Default value if key not found
        
        Returns:
            Config value or default
        
        Example:
            config.get('database', 'host')  # Returns 'localhost'
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def get_section(self, section):
        """
        Get entire config section
        
        Args:
            section (str): Section name (e.g., 'database', 'mqtt')
        
        Returns:
            dict: Section configuration
        """
        return self.config.get(section, {})
    
    def validate(self):
        """
        Validate that all required environment variables are set
        
        Returns:
            tuple: (is_valid, missing_vars)
        """
        required_vars = [
            'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
            'MQTT_BROKER', 'MQTT_PORT', 'MQTT_TOPIC'
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            logger.error("❌ Missing required environment variables:")
            for var in missing:
                logger.error(f"   - {var}")
            return False, missing
        
        logger.info("✓ All required environment variables are set")
        return True, []
    
    def print_config(self, hide_sensitive=True):
        """
        Print configuration (for debugging)
        
        Args:
            hide_sensitive (bool): Hide passwords in output
        """
        import copy
        
        config_copy = copy.deepcopy(self.config)
        
        if hide_sensitive:
            # Hide sensitive values
            if 'database' in config_copy and 'password' in config_copy['database']:
                config_copy['database']['password'] = '***HIDDEN***'
            if 'email' in config_copy and 'sender_password' in config_copy['email']:
                config_copy['email']['sender_password'] = '***HIDDEN***'
        
        print("\n" + "=" * 60)
        print("Current Configuration:")
        print("=" * 60)
        print(json.dumps(config_copy, indent=2))
        print("=" * 60 + "\n")


# Singleton instance
_config_instance = None


def get_config(config_path='config.json', env_path='.env'):
    """
    Get or create config loader instance (singleton pattern)
    
    Args:
        config_path (str): Path to config.json
        env_path (str): Path to .env file
    
    Returns:
        ConfigLoader: Config loader instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = ConfigLoader(config_path, env_path)
    
    return _config_instance


# Testing
def test_config():
    """Test configuration loading"""
    logger.info("=" * 60)
    logger.info("Testing Configuration Loader")
    logger.info("=" * 60)
    
    try:
        # Load config
        config = get_config()
        
        # Validate
        is_valid, missing = config.validate()
        
        if is_valid:
            # Print config (with hidden passwords)
            config.print_config(hide_sensitive=True)
            
            # Test accessing values
            logger.info("\nTesting config access:")
            logger.info(f"  Database host: {config.get('database', 'host')}")
            logger.info(f"  MQTT broker: {config.get('mqtt', 'broker')}")
            logger.info(f"  Email sender: {config.get('email', 'sender_email')}")
            logger.info(f"  Model threshold: {config.get('ai_model', 'threshold')}")
            
            logger.info("\n✅ Configuration test passed!")
        else:
            logger.error("\n❌ Configuration validation failed!")
            logger.error("Please check your .env file")
            
    except Exception as e:
        logger.error(f"\n❌ Configuration test failed: {e}")


if __name__ == "__main__":
    test_config()