from datetime import datetime,timezone
from .extensions import db
# from app import db 
class TimestampMixin:
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

# class Vehicle(db.Model, TimestampMixin):
#     __tablename__ = "vehicles"

#     id = db.Column(db.Integer, primary_key=True)
#     make = db.Column(db.String(64), index=True, nullable=False)
#     model = db.Column(db.String(64), index=True, nullable=False)
#     year = db.Column(db.String(16), index=True, nullable=True)
#     chassis_number = db.Column(db.String(64), unique=True, index=True, nullable=True)

#     parts = db.relationship("Part", back_populates="vehicle", lazy=True)


# class Part(db.Model, TimestampMixin):
#     __tablename__ = "parts"

#     id = db.Column(db.Integer, primary_key=True)
#     part_number = db.Column(db.String(128), unique=False, index=True, nullable=False)
#     name = db.Column(db.String(256), index=True, nullable=False)
#     brand = db.Column(db.String(128), index=True, nullable=True)
#     price = db.Column(db.Numeric(12, 2), nullable=True)
#     quantity_min = db.Column(db.Integer, nullable=True)

#     vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)
#     vehicle = db.relationship("Vehicle", back_populates="parts")


class Lead(db.Model, TimestampMixin):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_user_id = db.Column(db.String(64), index=True, nullable=False)
    user_locale = db.Column(db.String(16), nullable=True)
    intent = db.Column(db.String(64), nullable=True)
    query_text = db.Column(db.Text, nullable=True)
    assigned_agent = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(32), default="new", nullable=False)

class Stock(db.Model):
    __tablename__ = 'stock'

    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(500))
    brand_part_no = db.Column(db.String(255))     # ✔ cleaner than Text
    item_desc = db.Column(db.Text)
    price = db.Column(db.Float)                   # ✔ easier to use in python
    qty = db.Column(db.Integer)
    part_number = db.Column(db.String(255))
    brand = db.Column(db.String(255))
    unique_value = db.Column(db.Text)


 # or wherever your SQLAlchemy instance is

class IntentPrompt(db.Model):
    __tablename__ = "intent_prompts"

    id = db.Column(db.Integer, primary_key=True)
    intent_key = db.Column(db.String(100), unique=True, nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


# class MediaAttachment(db.Model, TimestampMixin):
#     __tablename__ = "media_attachments"

#     id = db.Column(db.Integer, primary_key=True)
#     lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True)
#     whatsapp_user_id = db.Column(db.String(64), index=True, nullable=False)
#     media_id = db.Column(db.String(128), nullable=False)
#     media_type = db.Column(db.String(32), nullable=False)
#     content_type = db.Column(db.String(64), nullable=True)
#     status = db.Column(db.String(32), default="pending", nullable=False)
#     extracted_text = db.Column(db.Text, nullable=True)
#     confidence = db.Column(db.Float, nullable=True)
#     language = db.Column(db.String(16), nullable=True)
#     error_message = db.Column(db.Text, nullable=True)

#     lead = db.relationship("Lead", back_populates="attachments")