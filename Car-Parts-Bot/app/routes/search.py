from flask import Blueprint, jsonify, request
from sqlalchemy import or_, and_
from ..extensions import db
# from ..models import Part, Vehicle
# from ..services.carparts_dubai_service import CarPartsDubaiService


search_bp = Blueprint("search", __name__)


# @search_bp.get("/part-number")
# def search_by_part_number():
#     part_number = request.args.get("q", type=str)
#     if not part_number:
#         return jsonify({"error": "Missing query 'q'"}), 400

#     parts = (
#         db.session.query(Part)
#         .filter(Part.part_number.ilike(f"%{part_number}%"))
#         .limit(100)
#         .all()
#     )

#     if parts:
#         return jsonify([_serialize_part(p) for p in parts])

#     external_service = CarPartsDubaiService()
#     external_results = external_service.find_by_part_number(part_number)
#     return jsonify(external_results)


# @search_bp.get("/chassis")
# def search_by_chassis_number():
#     chassis = request.args.get("q", type=str)
#     if not chassis:
#         return jsonify({"error": "Missing query 'q'"}), 400

#     vehicle = db.session.query(Vehicle).filter_by(chassis_number=chassis).first()
#     if not vehicle:
#         return jsonify({"vehicle": None, "parts": []})

#     parts = db.session.query(Part).filter(Part.vehicle_id == vehicle.id).limit(100).all()
#     return jsonify({
#         "vehicle": _serialize_vehicle(vehicle),
#         "parts": [_serialize_part(p) for p in parts],
#     })


# @search_bp.get("/car-part")
# def search_by_car_and_part():
#     car = request.args.get("car", type=str)
#     part = request.args.get("part", type=str)
#     if not car or not part:
#         return jsonify({"error": "Missing 'car' or 'part'"}), 400

#     make_model = [s.strip() for s in car.split(" ") if s.strip()]
#     vehicle_filters = []
#     if make_model:
#         vehicle_filters.append(or_(Vehicle.make.ilike(f"%{make_model[0]}%"), Vehicle.model.ilike(f"%{make_model[0]}%")))
#     if len(make_model) > 1:
#         vehicle_filters.append(or_(Vehicle.make.ilike(f"%{make_model[1]}%"), Vehicle.model.ilike(f"%{make_model[1]}%")))

#     vehicles = (db.session.query(Vehicle).filter(and_(*vehicle_filters)) if vehicle_filters else db.session.query(Vehicle))

#     parts = (
#         db.session.query(Part)
#         .join(Vehicle, Part.vehicle_id == Vehicle.id, isouter=True)
#         .filter(and_(Part.name.ilike(f"%{part}%"),
#                 or_(Vehicle.id.in_(v.id for v in vehicles.all()), Vehicle.id.is_(None)),
#             )
#         )
#         .limit(100)
#         .all()
#     )
#     return jsonify([_serialize_part(p) for p in parts])


# def _serialize_part(p: Part) -> dict:
#     return {
#         "id": p.id,
#         "part_number": p.part_number,
#         "name": p.name,
#         "brand": p.brand,
#         "price": float(p.price) if p.price is not None else None,
#         "quantity_min": p.quantity_min,
#         "vehicle": _serialize_vehicle(p.vehicle) if p.vehicle else None,
#     }


# def _serialize_vehicle(v: Vehicle | None) -> dict | None:
#     if not v:
#         return None
#     return {
#         "id": v.id,
#         "make": v.make,
#         "model": v.model,
#         "year": v.year,
#         "chassis_number": v.chassis_number,
#     }


