import os
from flask import Flask, render_template, jsonify
from config import Config

# Import Blueprints
from routes.auth_routes import auth_bp
from routes.otp_routes import otp_bp
from routes.product_routes import product_bp
from routes.machinery_routes import machinery_bp
from routes.order_routes import order_bp
from routes.booking_routes import booking_bp
from routes.admin_routes import admin_bp

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    public_static = os.path.join(base_dir, "public", "static")
    static_dir = public_static if os.path.isdir(public_static) else os.path.join(base_dir, "static")
    template_dir = os.path.join(base_dir, "templates")

    app = Flask(
        __name__,
        static_folder=static_dir,
        static_url_path="/static",
        template_folder=template_dir
    )
    app.config.from_object(Config)

    # Attach WhiteNoise for optimal static asset streaming on serverless & local
    try:
        from whitenoise import WhiteNoise
        app.wsgi_app = WhiteNoise(app.wsgi_app, root=static_dir, prefix="static/")
    except Exception:
        pass

    # Register API Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(otp_bp)
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
            "db_mode": Config.DB_MODE,
            "is_vercel": Config.IS_VERCEL
        })

    return app

# Top-level module Flask instance for Vercel WSGI entrypoint
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"======================================================")
    print(f"  AGRO FUTURE Platform running on http://127.0.0.1:{port}")
    print(f"======================================================")
    app.run(host="127.0.0.1", port=port, debug=os.getenv("FLASK_DEBUG") == "1")