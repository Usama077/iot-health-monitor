"""
Simple AI Model Training using Isolation Forest
NO TensorFlow required - uses only scikit-learn
"""

import pandas as pd
import numpy as np
import pickle
import os
import logging
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleAITrainer:
    def __init__(self, data_path='data/Synthetic_patient-HealthCare-Monitoring_dataset.csv'):
        """
        Initialize trainer with Isolation Forest
        
        Args:
            data_path (str): Path to CSV dataset
        """
        self.data_path = data_path
        self.model = None
        self.scaler = None
        
        # Ensure directories exist
        os.makedirs('models', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        logger.info("Simple AI Trainer initialized (Isolation Forest)")
    
    def load_and_preprocess_data(self):
        """
        Load dataset and extract normal data
        
        Returns:
            tuple: (X_train, X_test)
        """
        logger.info("=" * 60)
        logger.info("Loading dataset...")
        
        # Load CSV
        df = pd.read_csv(self.data_path)
        logger.info(f"✓ Loaded {len(df)} records")
        
        # Extract features
        df_filtered = df[['Heart Rate (bpm)', 'SpO2 Level (%)']].copy()
        df_filtered.columns = ['hr', 'spo2']
        
        logger.info(f"\nData Statistics:")
        logger.info(f"  HR  - Min: {df_filtered['hr'].min()}, Max: {df_filtered['hr'].max()}, Mean: {df_filtered['hr'].mean():.1f}")
        logger.info(f"  SpO2 - Min: {df_filtered['spo2'].min()}, Max: {df_filtered['spo2'].max()}, Mean: {df_filtered['spo2'].mean():.1f}")
        
        # Filter to NORMAL data only
        normal_mask = (
            (df_filtered['hr'] >= 60) & (df_filtered['hr'] <= 100) &
            (df_filtered['spo2'] >= 95) & (df_filtered['spo2'] <= 100)
        )
        
        df_normal = df_filtered[normal_mask].copy()
        
        logger.info(f"\n✓ Filtered to {len(df_normal)} NORMAL records")
        logger.info(f"  Normal percentage: {len(df_normal)/len(df_filtered)*100:.1f}%")
        
        # Convert to numpy
        X = df_normal[['hr', 'spo2']].values
        
        # Split data
        X_train, X_test = train_test_split(X, test_size=0.2, random_state=42)
        
        logger.info(f"\nData Split:")
        logger.info(f"  Training: {len(X_train)} samples")
        logger.info(f"  Testing: {len(X_test)} samples")
        
        # Normalize data
        logger.info("\nNormalizing data...")
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        logger.info("✓ Data preprocessing complete")
        logger.info("=" * 60)
        
        return X_train_scaled, X_test_scaled, X_test
    
    def train(self, X_train):
        """
        Train Isolation Forest model
        
        Args:
            X_train: Training data
        
        Returns:
            IsolationForest: Trained model
        """
        logger.info("\n" + "=" * 60)
        logger.info("Training Isolation Forest Model...")
        logger.info("=" * 60)
        
        # Create model
        # contamination=0.05 means expect 5% anomalies (95th percentile)
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
            verbose=0
        )
        
        # Train (fit on normal data)
        logger.info("\nTraining model on normal data...")
        self.model.fit(X_train)
        
        logger.info("✓ Training complete!")
        logger.info("\nModel Details:")
        logger.info(f"  Algorithm: Isolation Forest")
        logger.info(f"  Trees: 100")
        logger.info(f"  Contamination: 5%")
        
        return self.model
    
    def evaluate(self, X_test, X_test_original):
        """
        Evaluate model on test data
        
        Args:
            X_test: Scaled test data
            X_test_original: Original test data for display
        """
        logger.info("\n" + "=" * 60)
        logger.info("Evaluating Model...")
        logger.info("=" * 60)
        
        # Predict on test data (-1 = anomaly, 1 = normal)
        predictions = self.model.predict(X_test)
        
        # Get anomaly scores (lower = more anomalous)
        scores = self.model.score_samples(X_test)
        
        # Count predictions
        n_anomalies = np.sum(predictions == -1)
        n_normal = np.sum(predictions == 1)
        
        logger.info(f"\nTest Set Predictions:")
        logger.info(f"  Normal: {n_normal} ({n_normal/len(predictions)*100:.1f}%)")
        logger.info(f"  Anomalies: {n_anomalies} ({n_anomalies/len(predictions)*100:.1f}%)")
        logger.info(f"\nAnomaly Score Statistics:")
        logger.info(f"  Mean: {scores.mean():.4f}")
        logger.info(f"  Std: {scores.std():.4f}")
        logger.info(f"  Min: {scores.min():.4f}")
        logger.info(f"  Max: {scores.max():.4f}")
    
    def test_samples(self):
        """Test model with sample data"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Model with Sample Data...")
        logger.info("=" * 60)
        
        test_samples = [
            [75, 98],   # Normal
            [80, 97],   # Normal
            [135, 88],  # Anomaly: High HR, Low SpO2
            [45, 96],   # Anomaly: Low HR
            [120, 92],  # Anomaly: High HR, Low SpO2
        ]
        
        logger.info("\nTest Results:")
        logger.info("-" * 60)
        
        for i, sample in enumerate(test_samples):
            # Scale
            sample_scaled = self.scaler.transform([sample])
            
            # Predict
            prediction = self.model.predict(sample_scaled)[0]
            score = self.model.score_samples(sample_scaled)[0]
            
            is_anomaly = prediction == -1
            
            logger.info(f"\nSample {i+1}: HR={sample[0]}, SpO2={sample[1]}%")
            logger.info(f"  Anomaly Score: {score:.4f}")
            logger.info(f"  Status: {'🚨 ANOMALY' if is_anomaly else '✓ Normal'}")
        
        logger.info("\n" + "-" * 60)
    
    def save_model(self):
        """Save trained model and scaler"""
        logger.info("\n" + "=" * 60)
        logger.info("Saving Model and Scaler...")
        logger.info("=" * 60)
        
        # Save model
        model_path = 'models/isolation_forest.pkl'
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        logger.info(f"✓ Model saved to: {model_path}")
        
        # Save scaler
        scaler_path = 'models/scaler.pkl'
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        logger.info(f"✓ Scaler saved to: {scaler_path}")
        
        # Save model type
        model_type_path = 'models/model_type.txt'
        with open(model_type_path, 'w') as f:
            f.write('isolation_forest')
        logger.info(f"✓ Model type saved to: {model_type_path}")
        
        logger.info("\n✓ All artifacts saved successfully!")
    
    def plot_decision_boundary(self, X_train, X_test):
        """
        Plot decision boundary (optional visualization)
        
        Args:
            X_train: Training data (scaled)
            X_test: Test data (scaled)
        """
        try:
            logger.info("\nCreating visualization...")
            
            # Create mesh
            xx, yy = np.meshgrid(
                np.linspace(X_train[:, 0].min() - 1, X_train[:, 0].max() + 1, 100),
                np.linspace(X_train[:, 1].min() - 1, X_train[:, 1].max() + 1, 100)
            )
            
            # Predict on mesh
            Z = self.model.predict(np.c_[xx.ravel(), yy.ravel()])
            Z = Z.reshape(xx.shape)
            
            # Plot
            plt.figure(figsize=(10, 6))
            plt.contourf(xx, yy, Z, alpha=0.3, cmap='RdYlGn')
            
            # Plot training data
            plt.scatter(X_train[:, 0], X_train[:, 1], 
                       c='blue', s=20, alpha=0.5, label='Training (Normal)')
            
            # Plot test data
            predictions = self.model.predict(X_test)
            normal_test = X_test[predictions == 1]
            anomaly_test = X_test[predictions == -1]
            
            if len(normal_test) > 0:
                plt.scatter(normal_test[:, 0], normal_test[:, 1], 
                           c='green', s=50, marker='o', label='Test (Normal)')
            if len(anomaly_test) > 0:
                plt.scatter(anomaly_test[:, 0], anomaly_test[:, 1], 
                           c='red', s=100, marker='x', label='Test (Anomaly)')
            
            plt.xlabel('Heart Rate (scaled)')
            plt.ylabel('SpO2 (scaled)')
            plt.title('Isolation Forest - Decision Boundary')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            plot_path = 'models/decision_boundary.png'
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            logger.info(f"✓ Visualization saved to: {plot_path}")
            plt.close()
            
        except Exception as e:
            logger.warning(f"Could not create visualization: {e}")


def main():
    """Main training pipeline"""
    logger.info("\n")
    logger.info("=" * 60)
    logger.info("SIMPLE AI TRAINING PIPELINE (NO TENSORFLOW)")
    logger.info("Using: Isolation Forest Algorithm")
    logger.info("=" * 60)
    logger.info("\n")
    
    try:
        # Initialize trainer
        trainer = SimpleAITrainer()
        
        # Load and preprocess
        X_train, X_test, X_test_original = trainer.load_and_preprocess_data()
        
        # Train model
        trainer.train(X_train)
        
        # Evaluate
        trainer.evaluate(X_test, X_test_original)
        
        # Test samples
        trainer.test_samples()
        
        # Save
        trainer.save_model()
        
        # Visualize
        trainer.plot_decision_boundary(X_train, X_test)
        
        logger.info("\n")
        logger.info("=" * 60)
        logger.info("✅ TRAINING COMPLETE!")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Check models/ directory for saved files")
        logger.info("2. Use backend_simple_ai.py for inference")
        logger.info("3. Test with live sensor data")
        logger.info("")
        
    except Exception as e:
        logger.error(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()