from flask import Blueprint, request, jsonify, session
import uuid
import datetime
import random
from database import db

order_bp = Blueprint("order_bp", __name__)

@order_bp.route("/api/orders", methods=["POST"])
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
    if not user_id:
        # Fallback to demo customer
        demo_customer = db.get_user_by_email("customer.anita@agrofuture.com")
        user_id = demo_customer["id"] if demo_customer else None

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
def list_orders():
    user_id = session.get("user_id")
    user_role = session.get("role")
    
    # Query parameters can override for specific panel views
    role_param = request.args.get("role", user_role)
    
    if role_param == "farmer":
        farmer_id = request.args.get("farmer_id") or user_id
        if not farmer_id:
            demo_farmer = db.get_user_by_email("farmer.rajesh@agrofuture.com")
            farmer_id = demo_farmer["id"] if demo_farmer else None
        orders = db.get_orders(farmer_id=farmer_id)
    elif role_param == "customer":
        customer_id = request.args.get("customer_id") or user_id
        orders = db.get_orders(customer_id=customer_id)
    else:
        # Admin or global
        orders = db.get_orders()

    return jsonify({"orders": orders, "count": len(orders)})

@order_bp.route("/api/orders/<order_id>/status", methods=["PATCH"])
def update_status(order_id):
    data = request.get_json() or {}
    new_status = data.get("status", "").strip().lower()

    valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400

    db.update_order_status(order_id, new_status)
    return jsonify({"message": f"Order status updated to '{new_status}'."})
