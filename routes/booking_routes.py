from flask import Blueprint, request, jsonify, session
import uuid
import datetime
import random
from database import db

booking_bp = Blueprint("booking_bp", __name__)

@booking_bp.route("/api/bookings", methods=["POST"])
def book_machinery():
    data = request.get_json() or {}
    machinery_id = data.get("machinery_id")
    rental_type = data.get("rental_type", "hourly").strip().lower()
    start_datetime_str = data.get("start_datetime")
    delivery_location = data.get("delivery_location", "").strip()
    with_operator = bool(data.get("with_operator", False))
    notes = data.get("notes", "").strip()

    try:
        duration_units = float(data.get("duration_units", 1))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid duration."}), 400

    if not machinery_id or not delivery_location:
        return jsonify({"error": "Machinery selection and delivery location are required."}), 400

    if rental_type not in ["hourly", "daily"]:
        return jsonify({"error": "Rental type must be 'hourly' or 'daily'."}), 400

    machinery = db.get_machinery_by_id(machinery_id)
    if not machinery:
        return jsonify({"error": "Machinery not found."}), 404

    user_id = session.get("user_id")
    if not user_id:
        demo_customer = db.get_user_by_email("customer.anita@agrofuture.com")
        user_id = demo_customer["id"] if demo_customer else None

    # Calculate rates
    if rental_type == "hourly":
        rate_applied = float(machinery["hourly_rate"])
        operator_fee = float(machinery.get("operator_charge_per_hour", 0)) * duration_units if with_operator else 0.0
    else:
        rate_applied = float(machinery["daily_rate"])
        operator_fee = (float(machinery.get("operator_charge_per_hour", 0)) * 8) * duration_units if with_operator else 0.0

    base_subtotal = rate_applied * duration_units
    total_amount = round(base_subtotal + operator_fee, 2)

    # Commission calculation
    settings = db.get_platform_settings()
    machinery_comm_pct = float(settings.get("machinery_commission_percent", 10.0))
    commission_amount = round(total_amount * (machinery_comm_pct / 100.0), 2)
    seller_payout = round(total_amount - commission_amount, 2)

    # Date parsing
    now = datetime.datetime.utcnow()
    if start_datetime_str:
        try:
            start_dt = datetime.datetime.fromisoformat(start_datetime_str.replace("Z", "+00:00"))
        except Exception:
            start_dt = now + datetime.timedelta(days=1)
    else:
        start_dt = now + datetime.timedelta(days=1)

    if rental_type == "hourly":
        end_dt = start_dt + datetime.timedelta(hours=duration_units)
    else:
        end_dt = start_dt + datetime.timedelta(days=duration_units)

    booking_number = f"RN-{now.strftime('%Y%m')}-{random.randint(1000, 9999)}"

    booking_dict = {
        "id": str(uuid.uuid4()),
        "booking_number": booking_number,
        "customer_id": user_id,
        "machinery_id": machinery_id,
        "seller_id": machinery["seller_id"],
        "rental_type": rental_type,
        "start_datetime": start_dt.isoformat(),
        "end_datetime": end_dt.isoformat(),
        "duration_units": duration_units,
        "rate_applied": rate_applied,
        "with_operator": 1 if with_operator else 0,
        "operator_fee": round(operator_fee, 2),
        "total_amount": total_amount,
        "commission_amount": commission_amount,
        "seller_payout": seller_payout,
        "delivery_location": delivery_location,
        "notes": notes,
        "status": "pending",
        "payment_status": "pending",
        "created_at": now.isoformat()
    }

    db.create_booking(booking_dict)

    return jsonify({
        "message": f"Rental booking #{booking_number} requested successfully!",
        "booking": booking_dict
    }), 201

@booking_bp.route("/api/bookings", methods=["GET"])
def list_bookings():
    user_id = session.get("user_id")
    user_role = session.get("role")
    role_param = request.args.get("role", user_role)

    if role_param == "machinery_seller":
        seller_id = request.args.get("seller_id") or user_id
        if not seller_id:
            demo_seller = db.get_user_by_email("seller.kumar@agrofuture.com")
            seller_id = demo_seller["id"] if demo_seller else None
        bookings = db.get_bookings(seller_id=seller_id)
    elif role_param == "customer":
        customer_id = request.args.get("customer_id") or user_id
        bookings = db.get_bookings(customer_id=customer_id)
    else:
        # Admin or global
        bookings = db.get_bookings()

    return jsonify({"bookings": bookings, "count": len(bookings)})

@booking_bp.route("/api/bookings/<booking_id>/status", methods=["PATCH"])
def update_status(booking_id):
    data = request.get_json() or {}
    new_status = data.get("status", "").strip().lower()

    valid_statuses = ["pending", "approved", "in_progress", "completed", "rejected", "cancelled"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400

    db.update_booking_status(booking_id, new_status)
    return jsonify({"message": f"Rental booking status updated to '{new_status}'."})
