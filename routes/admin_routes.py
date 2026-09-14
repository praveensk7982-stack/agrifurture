from flask import Blueprint, request, jsonify, session
from database import db

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.route("/api/admin/metrics", methods=["GET"])
def get_metrics():
    metrics = db.get_admin_metrics()
    return jsonify({"metrics": metrics})

@admin_bp.route("/api/admin/commission-settings", methods=["GET"])
def get_commission_settings():
    settings = db.get_platform_settings()
    return jsonify({"settings": settings})

@admin_bp.route("/api/admin/commission-settings", methods=["PUT"])
def update_commission_settings():
    data = request.get_json() or {}
    try:
        produce_comm = float(data.get("produce_commission_percent", 5.0))
        machinery_comm = float(data.get("machinery_commission_percent", 10.0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid commission percentages."}), 400

    if produce_comm < 0 or produce_comm > 50 or machinery_comm < 0 or machinery_comm > 50:
        return jsonify({"error": "Commission must be between 0% and 50%."}), 400

    updated = db.update_platform_settings(produce_comm, machinery_comm)
    return jsonify({
        "message": "Platform commission settings updated successfully!",
        "settings": updated
    })

@admin_bp.route("/api/admin/users", methods=["GET"])
def list_users():
    role = request.args.get("role")
    users = db.get_all_users(role=role)
    safe_users = [{k: v for k, v in u.items() if k != "password_hash"} for u in users]
    return jsonify({"users": safe_users, "count": len(safe_users)})

@admin_bp.route("/api/admin/users/<user_id>/status", methods=["PATCH"])
def toggle_user_status(user_id):
    data = request.get_json() or {}
    status = data.get("status", "active")
    if status not in ["active", "suspended", "pending_verification"]:
        return jsonify({"error": "Invalid status."}), 400

    db.update_user_status(user_id, status)
    return jsonify({"message": f"User status set to '{status}'."})

@admin_bp.route("/api/admin/transactions", methods=["GET"])
def list_transactions():
    orders = db.get_orders()
    bookings = db.get_bookings()

    txns = []
    # Produce transactions
    for o in orders:
        txns.append({
            "id": o["id"],
            "ref_number": o["order_number"],
            "type": "produce_sale",
            "type_label": "Farm Produce Sale",
            "customer_name": o.get("customer_name") or "Customer",
            "gross_amount": float(o.get("total_amount", 0)),
            "platform_commission": float(o.get("total_commission", 0)),
            "vendor_net_payout": float(o.get("total_farmer_payout", 0)),
            "status": o.get("status", "pending"),
            "created_at": o.get("created_at")
        })

    # Machinery transactions
    for b in bookings:
        txns.append({
            "id": b["id"],
            "ref_number": b["booking_number"],
            "type": "machinery_rental",
            "type_label": f"Rental: {b.get('machinery_title', 'Machinery')}",
            "customer_name": b.get("customer_name") or "Customer",
            "gross_amount": float(b.get("total_amount", 0)),
            "platform_commission": float(b.get("commission_amount", 0)),
            "vendor_net_payout": float(b.get("seller_payout", 0)),
            "status": b.get("status", "pending"),
            "created_at": b.get("created_at")
        })

    # Sort newest first
    txns.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return jsonify({"transactions": txns, "count": len(txns)})
