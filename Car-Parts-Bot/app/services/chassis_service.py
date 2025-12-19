# """
# External chassis-to-vehicle API integration service.
# Converts chassis numbers to vehicle details (make, model, year).
# """
# import requests
# from typing import Any
# from flask import current_app
# from ..extensions import db
# from ..models import Vehicle


# class ChassisService:
#     """Service for integrating with external chassis-to-vehicle lookup APIs."""

#     def lookup_vehicle(self, chassis_number: str) -> dict[str, Any] | None:
#         """
#         Lookup vehicle details from chassis number using external API.
#         Returns: {
#             'make': str,
#             'model': str,
#             'year': str,
#             'chassis_number': str
#         } or None if not found
#         """
#         # Normalize chassis number
#         chassis_clean = chassis_number.strip().upper()

#         # Check if we already have it in DB
#         existing = db.session.query(Vehicle).filter_by(chassis_number=chassis_clean).first()
#         if existing:
#             return {
#                 "make": existing.make,
#                 "model": existing.model,
#                 "year": existing.year,
#                 "chassis_number": existing.chassis_number,
#             }

#         # Call external API
#         api_url = current_app.config.get("CHASSIS_API_BASE_URL")
#         api_key = current_app.config.get("CHASSIS_API_KEY")

#         if not api_url or not api_key:
#             # No external API configured - return None
#             return None

#         try:
#             # Example API call structure (adjust based on your actual API)
#             headers = {
#                 "Authorization": f"Bearer {api_key}",
#                 "Content-Type": "application/json",
#             }
#             params = {"chassis": chassis_clean}

#             response = requests.get(
#                 f"{api_url}/lookup", headers=headers, params=params, timeout=10
#             )
#             response.raise_for_status()
#             data = response.json()

#             # Extract vehicle info (adjust based on your API response format)
#             vehicle_data = {
#                 "make": data.get("make") or data.get("manufacturer"),
#                 "model": data.get("model"),
#                 "year": str(data.get("year") or data.get("year_of_manufacture", "")),
#                 "chassis_number": chassis_clean,
#             }

#             # Save to DB for future lookups
#             vehicle = Vehicle(
#                 make=vehicle_data["make"],
#                 model=vehicle_data["model"],
#                 year=vehicle_data["year"],
#                 chassis_number=chassis_clean,
#             )
#             db.session.add(vehicle)
#             db.session.commit()

#             return vehicle_data
#         except Exception as e:
#             # Log error but don't fail - return None
#             current_app.logger.error(f"Chassis API error: {e}")
#             return None

