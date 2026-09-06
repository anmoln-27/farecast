"""
backend/app/api/routers/prediction.py
---------------------------------------
GET /api/prediction — use the Phase 2 trained ML model to predict airfares.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from backend.app.ml.predictor import FarePredictor, InvalidInputError, ModelNotLoadedError, get_predictor
from backend.app.schemas.responses import PredictionRequest, PredictionResponse

router = APIRouter(prefix="/api", tags=["Prediction"])


@router.get("/prediction", response_model=PredictionResponse, summary="Predict airfare (ML model)")
def predict_fare(
    origin: str = Query(..., description="Origin city/IATA code, e.g. Delhi or DEL"),
    destination: str = Query(..., description="Destination city/IATA code, e.g. Mumbai or BOM"),
    airline: Optional[str] = Query(default="IndiGo"),
    cabin_class: Optional[str] = Query(default="Economy"),
    departure_time: Optional[str] = Query(default="Morning"),
    arrival_time: Optional[str] = Query(default="Afternoon"),
    stops: Optional[int] = Query(default=0, ge=0, le=2),
    duration_minutes: Optional[int] = Query(default=130, gt=0),
    days_left: Optional[int] = Query(default=20, ge=1, le=365),
    predictor: FarePredictor = Depends(get_predictor),
) -> PredictionResponse:
    """
    Predict airfare using the Phase 2 trained CatBoost / ensemble pipeline.
    Predictions are based on historical patterns; actual fares may differ.
    """
    try:
        result = predictor.predict_fare({
            "origin": origin,
            "destination": destination,
            "airline": airline,
            "cabin_class": cabin_class,
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "stops": stops,
            "duration_minutes": duration_minutes,
            "days_left": days_left,
        })
    except InvalidInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "ML model is not available. "
                "Please train the model first: python -m backend.app.ml.train"
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction error: {type(exc).__name__}")

    return PredictionResponse(**result)
