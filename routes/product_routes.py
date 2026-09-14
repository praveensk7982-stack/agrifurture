from flask import Blueprint, request, jsonify, session
import uuid
import datetime
from database import db

product_bp = Blueprint("product_bp", __name__)

DEFAULT_PRODUCE_IMAGES = {
    "fruits": "https://images.unsplash.com/photo-1619566636858-adf3ef46400b?w=600",
    "vegetables": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=600",
    "greens": "https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=600"
}

@product_bp.route("/api/products", methods=["GET"])
def list_products():
    category = request.args.get("category")
    farmer_id = request.args.get("farmer_id")
    search = request.args.get("search")
    status = request.args.get("status")

    products = db.get_products(category=category, farmer_id=farmer_id, search=search, status=status)
    return jsonify({"products": products, "count": len(products)})

@product_bp.route("/api/products/<product_id>", methods=["GET"])
def get_product(product_id):
    product = db.get_product_by_id(product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404
    return jsonify({"product": product})

@product_bp.route("/api/products", methods=["POST"])
def create_product():
    user_id = session.get("user_id")
    user_role = session.get("role")

    data = request.get_json() or {}
    farmer_id = data.get("farmer_id") or user_id

    # Fallback to demo farmer if not authenticated as farmer
    if not farmer_id or user_role not in ["farmer", "super_admin"]:
        demo_farmer = db.get_user_by_email("farmer.rajesh@agrofuture.com")
        if demo_farmer:
            farmer_id = demo_farmer["id"]

    title = data.get("title", "").strip()
    category = data.get("category", "").strip().lower()
    variety = data.get("variety", "").strip()
    description = data.get("description", "").strip()
    unit = data.get("unit", "kg").strip()
    
    try:
        price_per_unit = float(data.get("price_per_unit", 0))
        stock_quantity = float(data.get("stock_quantity", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid price or stock quantity."}), 400

    if not title or not category or price_per_unit <= 0:
        return jsonify({"error": "Title, category, and valid price are required."}), 400

    if category not in ["fruits", "vegetables", "greens"]:
        return jsonify({"error": "Category must be one of: fruits, vegetables, greens."}), 400

    is_organic = bool(data.get("is_organic", False))
    image_url = data.get("image_url") or DEFAULT_PRODUCE_IMAGES.get(category, DEFAULT_PRODUCE_IMAGES["vegetables"])

    product_dict = {
        "id": str(uuid.uuid4()),
        "farmer_id": farmer_id,
        "title": title,
        "category": category,
        "variety": variety,
        "description": description,
        "price_per_unit": price_per_unit,
        "unit": unit,
        "stock_quantity": stock_quantity,
        "is_organic": 1 if is_organic else 0,
        "image_url": image_url,
        "status": "active",
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    db.create_product(product_dict)
    return jsonify({"message": "Produce listing created successfully!", "product": product_dict}), 201

@product_bp.route("/api/products/<product_id>", methods=["PUT"])
def update_product(product_id):
    existing = db.get_product_by_id(product_id)
    if not existing:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json() or {}
    allowed_fields = ["title", "category", "variety", "description", "price_per_unit", "unit", "stock_quantity", "is_organic", "image_url", "status"]
    
    updates = {}
    for f in allowed_fields:
        if f in data:
            if f in ["price_per_unit", "stock_quantity"]:
                try:
                    updates[f] = float(data[f])
                except (ValueError, TypeError):
                    continue
            elif f == "is_organic":
                updates[f] = 1 if data[f] else 0
            else:
                updates[f] = data[f]

    if updates:
        db.update_product(product_id, updates)

    updated_product = db.get_product_by_id(product_id)
    return jsonify({"message": "Product updated successfully!", "product": updated_product})

@product_bp.route("/api/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    existing = db.get_product_by_id(product_id)
    if not existing:
        return jsonify({"error": "Product not found."}), 404

    db.delete_product(product_id)
    return jsonify({"message": "Product removed successfully!"})
