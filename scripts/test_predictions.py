"""
scripts/test_predictions.py
---------------------------
Demonstration script running sample predictions using the trained ML model.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ml.predictor import get_predictor

def main():
    predictor = get_predictor()
    queries = [
        {
            "origin": "Delhi",
            "destination": "Mumbai",
            "airline": "IndiGo",
            "cabin_class": "Economy",
            "days_left": 20,
            "departure_time": "Morning",
            "stops": 0,
        },
        {
            "origin": "Mumbai",
            "destination": "Bangalore",
            "airline": "Air India",
            "cabin_class": "Economy",
            "days_left": 5,
            "departure_time": "Evening",
            "stops": 0,
        },
        {
            "origin": "Delhi",
            "destination": "Bangalore",
            "airline": "Vistara",
            "cabin_class": "Business",
            "days_left": 15,
            "departure_time": "Morning",
            "stops": 1,
        },
        {
            "origin": "Kolkata",
            "destination": "Delhi",
            "airline": "AirAsia",
            "cabin_class": "Economy",
            "days_left": 2,
            "departure_time": "Early Morning",
            "stops": 0,
        },
    ]

    print("\n" + "=" * 65)
    print("  FARECAST — ML Predicted Fares based on Historical Data")
    print("=" * 65)
    for q in queries:
        res = predictor.predict_fare(q)
        print(f"\nInput: {q['origin']} -> {q['destination']} | {q['airline']} | {q['cabin_class']} | {q['days_left']} days left")
        print(f"  Predicted Fare : INR {res['predicted_fare']:,.2f}")
        print(f"  Prediction Range : INR {res['lower_estimate']:,.2f} - INR {res['upper_estimate']:,.2f}")
        print(f"  Margin (+/-)     : INR {res['prediction_uncertainty_margin']:,.2f}")
        print(f"  Data Basis       : {res['data_basis']}")
    print("\n" + "=" * 65)

if __name__ == "__main__":
    main()
