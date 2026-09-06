"""
backend/app/analytics/anomaly.py
---------------------------------
Fare anomaly detection logic.
Implements IQR (Interquartile Range) and Isolation Forest methods.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.db.models import Anomaly, AnomalySeverity, FareObservation

logger = logging.getLogger(__name__)


def detect_anomalies_iqr(
    session: Session,
    route_origin: str,
    route_destination: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Anomaly]:
    """
    Detect anomalies using the Interquartile Range (IQR) method.
    """
    query = session.query(
        FareObservation.id,
        FareObservation.origin,
        FareObservation.destination,
        FareObservation.airline_code,
        FareObservation.travel_date,
        FareObservation.days_left,
        FareObservation.fare
    ).filter(
        FareObservation.origin == route_origin,
        FareObservation.destination == route_destination
    )
    
    if start_date:
        query = query.filter(FareObservation.travel_date >= start_date)
    if end_date:
        query = query.filter(FareObservation.travel_date <= end_date)
        
    records = query.all()
    if not records or len(records) < 10:
        logger.warning("Not enough records for IQR anomaly detection.")
        return []
        
    df = pd.DataFrame([{
        "id": r.id, 
        "origin": r.origin, 
        "destination": r.destination, 
        "airline": r.airline_code,
        "travel_date": r.travel_date,
        "days_left": r.days_left,
        "fare": r.fare
    } for r in records])
    
    q1 = df["fare"].quantile(0.25)
    q3 = df["fare"].quantile(0.75)
    iqr = q3 - q1
    
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    median_fare = df["fare"].median()
    
    anomalies_to_save = []
    
    for _, row in df.iterrows():
        fare = row["fare"]
        if fare < lower_bound or fare > upper_bound:
            # It's an anomaly
            severity = AnomalySeverity.HIGH if (fare > upper_bound * 1.5 or fare < lower_bound * 0.5) else AnomalySeverity.WATCH
            deviation = ((fare - median_fare) / median_fare) * 100.0 if median_fare > 0 else 0.0
            
            # Simple scoring: how many IQRs away
            if fare > upper_bound:
                score = (fare - q3) / iqr
            else:
                score = (q1 - fare) / iqr
                
            anomaly = Anomaly(
                fare_observation_id=row["id"],
                route=f"{row['origin']}-{row['destination']}",
                airline=row["airline"],
                travel_date=row["travel_date"],
                days_left=row["days_left"],
                observed_fare=fare,
                expected_fare=median_fare,
                deviation_percentage=deviation,
                anomaly_score=score,
                severity=severity,
                method="IQR",
                description=f"Fare {fare} is outside typical range ({lower_bound:.1f} to {upper_bound:.1f})."
            )
            anomalies_to_save.append(anomaly)
            
    if anomalies_to_save:
        # Avoid duplicating same method on same observation
        obs_ids = [a.fare_observation_id for a in anomalies_to_save]
        session.query(Anomaly).filter(
            Anomaly.fare_observation_id.in_(obs_ids),
            Anomaly.method == "IQR"
        ).delete(synchronize_session=False)
        
        session.bulk_save_objects(anomalies_to_save)
        session.commit()
        logger.info(f"Detected {len(anomalies_to_save)} anomalies using IQR.")
        
    return anomalies_to_save


def detect_anomalies_isolation_forest(
    session: Session,
    route_origin: str,
    route_destination: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Anomaly]:
    """
    Detect anomalies using scikit-learn's Isolation Forest.
    """
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        logger.error("scikit-learn is required for Isolation Forest.")
        return []
        
    query = session.query(
        FareObservation.id,
        FareObservation.origin,
        FareObservation.destination,
        FareObservation.airline_code,
        FareObservation.travel_date,
        FareObservation.days_left,
        FareObservation.fare
    ).filter(
        FareObservation.origin == route_origin,
        FareObservation.destination == route_destination
    )
    
    if start_date:
        query = query.filter(FareObservation.travel_date >= start_date)
    if end_date:
        query = query.filter(FareObservation.travel_date <= end_date)
        
    records = query.all()
    if not records or len(records) < 50:  # IF needs more data points
        logger.warning("Not enough records for Isolation Forest anomaly detection.")
        return []
        
    df = pd.DataFrame([{
        "id": r.id, 
        "origin": r.origin, 
        "destination": r.destination, 
        "airline": r.airline_code,
        "travel_date": r.travel_date,
        "days_left": r.days_left if r.days_left is not None else 30, # Default if missing
        "fare": r.fare
    } for r in records])
    
    # We use fare and days_left as features
    features = df[["fare", "days_left"]].copy()
    
    # Simple median imputation for any stray NaNs
    features.fillna(features.median(), inplace=True)
    
    clf = IsolationForest(contamination=0.05, random_state=42)
    df["anomaly_label"] = clf.fit_predict(features)
    
    # anomaly_label is -1 for outliers and 1 for inliers
    df["anomaly_score_raw"] = clf.decision_function(features) # Lower is more anomalous
    
    median_fare = df["fare"].median()
    anomalies_to_save = []
    
    outliers = df[df["anomaly_label"] == -1]
    
    for _, row in outliers.iterrows():
        fare = row["fare"]
        deviation = ((fare - median_fare) / median_fare) * 100.0 if median_fare > 0 else 0.0
        
        # Convert raw score (negative) to a positive magnitude for interpretability
        score = abs(row["anomaly_score_raw"]) * 10 
        
        severity = AnomalySeverity.HIGH if score > 1.5 else AnomalySeverity.WATCH
        
        anomaly = Anomaly(
            fare_observation_id=row["id"],
            route=f"{row['origin']}-{row['destination']}",
            airline=row["airline"],
            travel_date=row["travel_date"],
            days_left=row["days_left"],
            observed_fare=fare,
            expected_fare=median_fare,
            deviation_percentage=deviation,
            anomaly_score=score,
            severity=severity,
            method="IsolationForest",
            description=f"Flagged by Isolation Forest model (fare {fare}, days_left {row['days_left']})."
        )
        anomalies_to_save.append(anomaly)
        
    if anomalies_to_save:
        obs_ids = [a.fare_observation_id for a in anomalies_to_save]
        session.query(Anomaly).filter(
            Anomaly.fare_observation_id.in_(obs_ids),
            Anomaly.method == "IsolationForest"
        ).delete(synchronize_session=False)
        
        session.bulk_save_objects(anomalies_to_save)
        session.commit()
        logger.info(f"Detected {len(anomalies_to_save)} anomalies using Isolation Forest.")
        
    return anomalies_to_save
