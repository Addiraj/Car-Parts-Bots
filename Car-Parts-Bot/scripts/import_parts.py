import csv
import os
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models import Part, Vehicle


def import_csv(file_path: str) -> None:
    app = create_app()
    with app.app_context():
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                make = (row.get("make") or row.get("car_make") or "").strip()
                model = (row.get("model") or row.get("car_model") or "").strip()
                year = (row.get("year") or "").strip()
                part_number = (row.get("part_number") or row.get("sku") or "").strip()
                name = (row.get("name") or row.get("part_name") or "").strip()
                brand = (row.get("brand") or "").strip()
                price_str = (row.get("price") or "").strip()
                qty_min_str = (row.get("quantity_min") or row.get("qty_min") or "").strip()

                if not part_number or not name:
                    continue

                vehicle = None
                if make or model or year:
                    vehicle = (
                        db.session.query(Vehicle)
                        .filter_by(make=make, model=model, year=year or None)
                        .first()
                    )
                    if not vehicle:
                        vehicle = Vehicle(make=make, model=model, year=year or None)
                        db.session.add(vehicle)
                        db.session.flush()

                price = None
                if price_str:
                    try:
                        price = Decimal(price_str)
                    except Exception:
                        price = None

                qty_min = None
                if qty_min_str:
                    try:
                        qty_min = int(qty_min_str)
                    except Exception:
                        qty_min = None

                part = Part(
                    part_number=part_number,
                    name=name,
                    brand=brand or None,
                    price=price,
                    quantity_min=qty_min,
                    vehicle_id=vehicle.id if vehicle else None,
                )
                db.session.add(part)

            db.session.commit()


if __name__ == "__main__":
    path = os.environ.get("PARTS_CSV", "./data/parts.csv")
    import_csv(path)


