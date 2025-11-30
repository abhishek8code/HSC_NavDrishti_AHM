"""
AI Traffic Prediction Module
Uses machine learning models for congestion and speed forecasting
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import joblib
import os

class TrafficPredictor:
    """
    Traffic prediction using Random Forest and statistical methods
    For production, this would use LSTM/ARIMA, but RF provides quick baseline
    """
    
    def __init__(self, model_path: str = "models/"):
        self.model_path = model_path
        self.speed_model = None
        self.congestion_model = None
        self.scaler = StandardScaler()
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        
        # Create models directory if it doesn't exist
        os.makedirs(model_path, exist_ok=True)
        
    def prepare_features(self, timestamp: datetime, road_segment_id: int, 
                        historical_data: pd.DataFrame = None) -> np.ndarray:
        """
        Extract time-based features from timestamp
        In production, would include weather, events, etc.
        """
        features = {
            'hour': timestamp.hour,
            'day_of_week': timestamp.weekday(),
            'day_of_month': timestamp.day,
            'month': timestamp.month,
            'is_weekend': 1 if timestamp.weekday() >= 5 else 0,
            'is_rush_hour': 1 if timestamp.hour in [7, 8, 9, 17, 18, 19] else 0,
            'is_night': 1 if timestamp.hour < 6 or timestamp.hour > 22 else 0,
            'road_segment_id': road_segment_id
        }
        
        # Add historical averages if available
        if historical_data is not None and len(historical_data) > 0:
            features['hist_avg_speed'] = historical_data['average_speed'].mean()
            features['hist_std_speed'] = historical_data['average_speed'].std()
            features['hist_avg_vehicles'] = historical_data['vehicle_count'].mean()
        else:
            features['hist_avg_speed'] = 40.0  # Default baseline
            features['hist_std_speed'] = 10.0
            features['hist_avg_vehicles'] = 25.0
        
        return np.array(list(features.values())).reshape(1, -1)
    
    def train_speed_model(self, training_data: pd.DataFrame):
        """
        Train Random Forest model for speed prediction
        """
        if len(training_data) < 50:
            raise ValueError("Insufficient training data (need at least 50 samples)")
        
        # Prepare features
        X = []
        y = training_data['average_speed'].values
        
        for idx, row in training_data.iterrows():
            timestamp = pd.to_datetime(row['timestamp'])
            features = self.prepare_features(
                timestamp, 
                row.get('road_segment_id', 1),
                None  # No historical context during training
            )
            X.append(features[0])
        
        X = np.array(X)
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.speed_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self.speed_model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_score = self.speed_model.score(X_train_scaled, y_train)
        test_score = self.speed_model.score(X_test_scaled, y_test)
        
        print(f"Speed Model - Train R²: {train_score:.3f}, Test R²: {test_score:.3f}")
        
        # Save model
        self.save_model('speed_model')
        
        return test_score
    
    def predict_speed(self, timestamp: datetime, road_segment_id: int, 
                     historical_data: pd.DataFrame = None) -> Dict:
        """
        Predict average speed for given timestamp and road segment
        """
        if self.speed_model is None:
            # Try to load saved model
            if not self.load_model('speed_model'):
                # Return baseline prediction if no model
                return {
                    'predicted_speed': 40.0,
                    'confidence': 0.5,
                    'model': 'baseline',
                    'lower_bound': 30.0,
                    'upper_bound': 50.0
                }
        
        # Prepare features
        features = self.prepare_features(timestamp, road_segment_id, historical_data)
        features_scaled = self.scaler.transform(features)
        
        # Predict
        prediction = self.speed_model.predict(features_scaled)[0]
        
        # Estimate confidence using tree variance
        tree_predictions = np.array([
            tree.predict(features_scaled)[0] 
            for tree in self.speed_model.estimators_
        ])
        std = np.std(tree_predictions)
        confidence = max(0.0, min(1.0, 1.0 - (std / 20.0)))  # Normalize to 0-1
        
        return {
            'predicted_speed': round(float(prediction), 2),
            'confidence': round(confidence, 3),
            'model': 'random_forest',
            'lower_bound': round(float(prediction - 2 * std), 2),
            'upper_bound': round(float(prediction + 2 * std), 2),
            'std_dev': round(float(std), 2)
        }
    
    def predict_congestion(self, predicted_speed: float) -> str:
        """
        Map predicted speed to congestion state
        """
        if predicted_speed >= 50:
            return 'free_flow'
        elif predicted_speed >= 35:
            return 'light'
        elif predicted_speed >= 20:
            return 'moderate'
        elif predicted_speed >= 10:
            return 'heavy'
        else:
            return 'severe'
    
    def detect_anomalies(self, current_data: pd.DataFrame, 
                        training_data: pd.DataFrame = None) -> List[Dict]:
        """
        Detect traffic anomalies using Isolation Forest
        """
        if training_data is not None and len(training_data) > 50:
            # Train anomaly detector on historical data
            X_train = training_data[['average_speed', 'vehicle_count']].values
            self.anomaly_detector.fit(X_train)
        
        # Detect anomalies in current data
        X_current = current_data[['average_speed', 'vehicle_count']].values
        anomaly_scores = self.anomaly_detector.decision_function(X_current)
        predictions = self.anomaly_detector.predict(X_current)
        
        anomalies = []
        for idx, (score, pred) in enumerate(zip(anomaly_scores, predictions)):
            if pred == -1:  # Anomaly detected
                row = current_data.iloc[idx]
                
                # Determine anomaly type
                if row['average_speed'] < 10:
                    anomaly_type = 'severe_slowdown'
                    severity = 'critical'
                elif row['vehicle_count'] > 100:
                    anomaly_type = 'high_volume'
                    severity = 'high'
                else:
                    anomaly_type = 'unusual_pattern'
                    severity = 'medium'
                
                anomalies.append({
                    'road_segment_id': row.get('road_segment_id', 0),
                    'timestamp': row['timestamp'],
                    'anomaly_type': anomaly_type,
                    'severity': severity,
                    'anomaly_score': round(float(-score), 3),  # Convert to positive
                    'speed': row['average_speed'],
                    'vehicle_count': row['vehicle_count']
                })
        
        return anomalies
    
    def recommend_route(self, origin: Tuple[float, float], 
                       destination: Tuple[float, float],
                       vehicle_type: str = 'car',
                       time_preference: str = 'fastest') -> Dict:
        """
        Recommend optimal route based on predictions
        Simple heuristic-based recommendation
        In production, would use collaborative filtering + ML
        """
        # Calculate base scores
        time_score = 0.85 if time_preference == 'fastest' else 0.60
        distance_score = 0.75
        safety_score = 0.90
        traffic_score = 0.70  # Would come from prediction
        
        # Adjust for vehicle type
        if vehicle_type == 'bus':
            safety_score *= 1.1  # Prefer safer routes
            traffic_score *= 0.9  # More sensitive to traffic
        elif vehicle_type == 'emergency':
            time_score *= 1.2  # Prioritize speed
        
        # Combined confidence
        confidence = (time_score * 0.3 + distance_score * 0.25 + 
                     safety_score * 0.2 + traffic_score * 0.25)
        
        return {
            'confidence': round(confidence, 3),
            'factors': {
                'time_score': round(time_score, 3),
                'distance_score': round(distance_score, 3),
                'safety_score': round(safety_score, 3),
                'predicted_traffic_score': round(traffic_score, 3)
            },
            'estimated_time_min': 25,
            'estimated_distance_km': 12.5,
            'route_type': 'ai_recommended'
        }
    
    def save_model(self, model_name: str):
        """Save trained model to disk"""
        if model_name == 'speed_model' and self.speed_model is not None:
            joblib.dump(self.speed_model, os.path.join(self.model_path, 'speed_model.pkl'))
            joblib.dump(self.scaler, os.path.join(self.model_path, 'scaler.pkl'))
            print(f"Model saved to {self.model_path}")
    
    def load_model(self, model_name: str) -> bool:
        """Load trained model from disk"""
        try:
            if model_name == 'speed_model':
                model_file = os.path.join(self.model_path, 'speed_model.pkl')
                scaler_file = os.path.join(self.model_path, 'scaler.pkl')
                
                if os.path.exists(model_file) and os.path.exists(scaler_file):
                    self.speed_model = joblib.load(model_file)
                    self.scaler = joblib.load(scaler_file)
                    print(f"Model loaded from {self.model_path}")
                    return True
        except Exception as e:
            print(f"Error loading model: {e}")
        
        return False
    
    def get_model_stats(self) -> Dict:
        """Get model performance statistics"""
        return {
            'speed_model_loaded': self.speed_model is not None,
            'last_trained': datetime.now().isoformat() if self.speed_model else None,
            'model_type': 'random_forest',
            'features_count': 11,
            'anomaly_detector_ready': True
        }


# Global predictor instance
predictor = TrafficPredictor(model_path="Traffic_Backend/models/")
