"""
backend/app/analytics/index_engine.py
-------------------------------------
Calculates a PROTOTYPE Airfare Price Index.
This is strictly a prototype and NOT an official Government of India index.

Index = (current average fare / baseline average fare) * 100
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Dict, Optional, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db.models import AirfareIndex, FareObservation

logger = logging.getLogger(__name__)


def calculate_baseline(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, float]:
    """
    Calculate the baseline average fare per route.
    If dates are provided, filters the historical records by travel_date.
    Returns a dictionary mapping route (origin-destination) to baseline average fare.
    """
    query = session.query(
        FareObservation.origin,
        FareObservation.destination,
        func.avg(FareObservation.fare).label("avg_fare"),
        func.count(FareObservation.id).label("count")
    )
    
    if start_date:
        query = query.filter(FareObservation.travel_date >= start_date)
    if end_date:
        query = query.filter(FareObservation.travel_date <= end_date)
        
    # Group by origin, destination
    results = query.group_by(FareObservation.origin, FareObservation.destination).all()
    
    baseline_fares = {}
    for origin, dest, avg_fare, count in results:
        # Ignore routes with extremely low data volume for baselining
        if count >= 10 and avg_fare is not None:
            route = f"{origin}-{dest}"
            baseline_fares[route] = float(avg_fare)
            
    return baseline_fares


def generate_price_index(
    session: Session,
    target_start_date: date,
    target_end_date: date,
    period_label: str,
    baseline_fares: Dict[str, float],
    baseline_period_label: str = "custom",
    period_type: str = "month"
) -> List[AirfareIndex]:
    """
    Calculate the PROTOTYPE Airfare Price Index for a specific target period.
    """
    query = session.query(
        FareObservation.origin,
        FareObservation.destination,
        func.avg(FareObservation.fare).label("avg_fare"),
        func.count(FareObservation.id).label("count")
    ).filter(
        FareObservation.travel_date >= target_start_date,
        FareObservation.travel_date <= target_end_date
    ).group_by(
        FareObservation.origin,
        FareObservation.destination
    )
    
    results = query.all()
    
    indices_to_save = []
    
    for origin, dest, avg_fare, count in results:
        if count < 5 or avg_fare is None:
            continue
            
        route = f"{origin}-{dest}"
        baseline_fare = baseline_fares.get(route)
        
        if baseline_fare is None or baseline_fare <= 0:
            continue
            
        index_value = (float(avg_fare) / baseline_fare) * 100.0
        
        # Create DB record
        record = AirfareIndex(
            route=route,
            airline="ALL",
            period=period_label,
            period_type=period_type,
            avg_fare=float(avg_fare),
            baseline_fare=baseline_fare,
            index_value=index_value,
            baseline_period=baseline_period_label,
            observation_count=count,
            weight_source="PROTOTYPE - Equal Weight Assumption",
            data_source="PROTOTYPE Airfare Index Engine"
        )
        indices_to_save.append(record)
        
    if indices_to_save:
        # Remove existing records for this exact period/type to prevent duplicates
        session.query(AirfareIndex).filter_by(
            period=period_label, 
            period_type=period_type,
            data_source="PROTOTYPE Airfare Index Engine"
        ).delete()
        
        session.bulk_save_objects(indices_to_save)
        session.commit()
        logger.info(f"Generated PROTOTYPE Airfare Index for {len(indices_to_save)} routes (period {period_label}).")
        
    return indices_to_save
