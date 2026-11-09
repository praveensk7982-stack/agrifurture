from flask import Blueprint, request, jsonify, session
import uuid
import datetime
import random
from database import db
from routes.auth_routes import login_required, role_required

order_bp = Blueprint("order_bp", __name__)

@order_bp.route("/api/orders", methods=["POST"])
@role_required("customer", "super_admin")
def place_order():
    data = request.get_json() or {}
    items_data = data.get("items", [])
    shipping_address = data.get("shipping_address", "").strip()
    contact_phone = data.get("contact_phone", "").strip()
    payment_method = data.get("payment_method", "cod")

    if not items_data:
        return jsonify({"error": "Cart is empty. Please add items before checkout."}), 400

    if not shipping_address or not contact_phone:
        return jsonify({"error": "Shipping address and contact phone number are required."}), 400

    user_id = session.get("user_id")

    # Fetch platform commission settings
    settings = db.get_platform_settings()
    produce_comm_pct = float(settings.get("produce_commission_percent", 5.0))

    total_amount = 0.0
    total_commission = 0.0
    total_farmer_payout = 0.0
    order_items = []

    for item in items_data:
        p_id = item.get("product_id")
        qty = float(item.get("quantity", 1))
        
        product = db.get_product_by_id(p_id)
        if not product:
            return jsonify({"error": f"Product with ID {p_id} not found."}), 404

        price = float(product["price_per_unit"])
        subtotal = round(price * qty, 2)
        comm = round(subtotal * (produce_comm_pct / 100.0), 2)
        farmer_net = round(subtotal - comm, 2)

        total_amount += subtotal
        total_commission += comm
        total_farmer_payout += farmer_net

        order_items.append({
            "id": str(uuid.uuid4()),
            "product_id": p_id,
            "farmer_id": product["farmer_id"],
            "quantity": qty,
            "unit_price": price,
            "subtotal": subtotal,
            "commission_amount": comm,
            "farmer_earnings": farmer_net,
            "created_at": datetime.datetime.utcnow().isoformat()
        })

    order_number = f"ORD-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

    order_dict = {
        "id": str(uuid.uuid4()),
        "order_number": order_number,
        "customer_id": user_id,
        "total_amount": round(total_amount, 2),
        "total_commission": round(total_commission, 2),
        "total_farmer_payout": round(total_farmer_payout, 2),
        "shipping_address": shipping_address,
        "contact_phone": contact_phone,
        "payment_method": payment_method,
        "payment_status": "paid" if payment_method in ["upi", "card"] else "pending",
        "status": "pending",
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    db.create_order(order_dict, order_items)

    return jsonify({
        "message": f"Order #{order_number} placed successfully!",
        "order": order_dict,
        "items": order_items
    }), 201

@order_bp.route("/api/orders", methods=["GET"])
@login_required
def list_orders():
    user_id = session.get("user_id")
    active_role = session.get("active_role") or session.get("role")

    if not active_role:
        return jsonify({"error": "Forbidden: No active workspace."}), 403

    if active_role == "farmer":
        if not db.user_has_role(user_id, "farmer"):
            return jsonify({"error": "Forbidden: You do not have the farmer workspace."}), 403
        orders = db.get_orders(farmer_id=user_id)
    elif active_role == "customer":
        if not db.user_has_role(user_id, "customer"):
            return jsonify({"error": "Forbidden: You do not have the customer workspace."}), 403
        orders = db.get_orders(customer_id=user_id)
    elif active_role == "super_admin":
        f_id = request.args.get("farmer_id")
        c_id = request.args.get("customer_id")
        orders = db.get_orders(farmer_id=f_id, customer_id=c_id)
    else:
        orders = db.get_orders(customer_id=user_id)

    return jsonify({"orders": orders, "count": len(orders)})

@order_bp.route("/api/orders/<order_id>/status", methods=["PATCH"])
@role_required("farmer", "super_admin")
def update_status(order_id):
    data = request.get_json() or {}
    new_status = data.get("status", "").strip().lower()

    valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400

    db.update_order_status(order_id, new_status)
    return jsonify({"message": f"Order status updated to '{new_status}'."})
