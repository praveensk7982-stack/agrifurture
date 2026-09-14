from flask import Blueprint, request, jsonify, session
import uuid
import datetime
from database import db

machinery_bp = Blueprint("machinery_bp", __name__)

DEFAULT_MACHINERY_IMAGES = {
    "tractor": "https://images.unsplash.com/photo-1592878904946-b3cd8ae243d0?w=600",
    "harvester": "https://images.unsplash.com/photo-1595838742456-424a73740263?w=600",
    "water_pump": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=600",
    "bulldozer": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600",
    "power_tiller": "https://images.unsplash.com/photo-1530267981375-f0de937f5f13?w=600",
    "sprayer": "https://images.unsplash.com/photo-1589923188900-85dae523342b?w=600"
}

@machinery_bp.route("/api/machinery", methods=["GET"])
def list_machinery():
    category = request.args.get("category")
    seller_id = request.args.get("seller_id")
    search = request.args.get("search")
    available_only = request.args.get("available_only", "").lower() == "true"

    fleet = db.get_machinery(category=category, seller_id=seller_id, search=search, available_only=available_only)
    return jsonify({"machinery": fleet, "count": len(fleet)})

@machinery_bp.route("/api/machinery/<machinery_id>", methods=["GET"])
def get_machinery_item(machinery_id):
    item = db.get_machinery_by_id(machinery_id)
    if not item:
        return jsonify({"error": "Machinery not found."}), 404
    return jsonify({"machinery": item})

@machinery_bp.route("/api/machinery", methods=["POST"])
def create_machinery_item():
    user_id = session.get("user_id")
    user_role = session.get("role")

    data = request.get_json() or {}
    seller_id = data.get("seller_id") or user_id

    # Fallback to demo seller if not authenticated as machinery seller
    if not seller_id or user_role not in ["machinery_seller", "super_admin"]:
        demo_seller = db.get_user_by_email("seller.kumar@agrofuture.com")
        if demo_seller:
            seller_id = demo_seller["id"]

    title = data.get("title", "").strip()
    category = data.get("category", "").strip().lower()
    model_info = data.get("model_info", "").strip()
    specifications = data.get("specifications", "").strip()
    location = data.get("location", "").strip() or "Tamil Nadu"

    try:
        hourly_rate = float(data.get("hourly_rate", 0))
        daily_rate = float(data.get("daily_rate", 0))
        operator_charge = float(data.get("operator_charge_per_hour", 0.0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid hourly or daily rental rates."}), 400

    if not title or not category or hourly_rate <= 0 or daily_rate <= 0:
        return jsonify({"error": "Title, category, hourly rate, and daily rate are required."}), 400

    includes_operator = bool(data.get("includes_operator", False))
    image_url = data.get("image_url") or DEFAULT_MACHINERY_IMAGES.get(category, DEFAULT_MACHINERY_IMAGES["tractor"])

    machinery_dict = {
        "id": str(uuid.uuid4()),
        "seller_id": seller_id,
        "title": title,
        "category": category,
        "model_info": model_info,
        "specifications": specifications,
        "hourly_rate": hourly_rate,
        "daily_rate": daily_rate,
        "location": location,
        "includes_operator": 1 if includes_operator else 0,
        "operator_charge_per_hour": operator_charge,
        "image_url": image_url,
        "is_available": 1,
        "status": "active",
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    db.create_machinery(machinery_dict)
    return jsonify({"message": "Machinery listed successfully for rental!", "machinery": machinery_dict}), 201

@machinery_bp.route("/api/machinery/<machinery_id>", methods=["PUT"])
def update_machinery_item(machinery_id):
    existing = db.get_machinery_by_id(machinery_id)
    if not existing:
        return jsonify({"error": "Machinery not found."}), 404

    data = request.get_json() or {}
    allowed_fields = ["title", "category", "model_info", "specifications", "hourly_rate", "daily_rate", "location", "includes_operator", "operator_charge_per_hour", "image_url", "is_available", "status"]

    updates = {}
    for f in allowed_fields:
        if f in data:
            if f in ["hourly_rate", "daily_rate", "operator_charge_per_hour"]:
                try:
                    updates[f] = float(data[f])
                except (ValueError, TypeError):
                    continue
            elif f in ["includes_operator", "is_available"]:
                updates[f] = 1 if data[f] else 0
            else:
                updates[f] = data[f]

    if updates:
        db.update_machinery(machinery_id, updates)

    updated_item = db.get_machinery_by_id(machinery_id)
    return jsonify({"message": "Machinery updated successfully!", "machinery": updated_item})

@machinery_bp.route("/api/machinery/<machinery_id>", methods=["DELETE"])
def delete_machinery_item(machinery_id):
    existing = db.get_machinery_by_id(machinery_id)
    if not existing:
        return jsonify({"error": "Machinery not found."}), 404

    db.delete_machinery(machinery_id)
    return jsonify({"message": "Machinery removed from catalog!"})
