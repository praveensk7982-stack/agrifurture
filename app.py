import os
from flask import Flask, render_template, jsonify, send_from_directory
from flask_cors import CORS
from config import Config

# Import Blueprints
from routes.auth_routes import auth_bp
from routes.product_routes import product_bp
from routes.machinery_routes import machinery_bp
from routes.order_routes import order_bp
from routes.booking_routes import booking_bp
from routes.admin_routes import admin_bp

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    CORS(app, supports_credentials=True)

    # Register API Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(machinery_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health")
    def health_check():
        from database import db
        return jsonify({
            "status": "online",
            "platform": "AGRO FUTURE",
            "version": "1.0.0",
            "supabase_active": db.use_supabase,
            "db_mode": Config.DB_MODE
        })

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    print(f"======================================================")
    print(f"  AGRO FUTURE Platform running on http://127.0.0.1:{port}")
    print(f"======================================================")
    app.run(host="0.0.0.0", port=port, debug=True)
