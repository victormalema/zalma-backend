import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from routes.auth_routes import auth_bp
from routes.products_routes import products_bp
from routes.cart_routes import cart_bp
from routes.preorder_routes import preorder_bp
from routes.orders_routes import orders_bp
from routes.rewards_routes import rewards_bp
from routes.badges_routes import badges_bp
from routes.wall_routes import wall_bp
from routes.wraps_routes import wraps_bp
from routes.tiers_routes import tiers_bp
from routes.social_routes import social_bp
from routes.unboxing_routes import unboxing_bp
from routes.admin_routes import admin_bp
from routes.payments_routes import payments_bp
def create_app():
    Config.validate()

    app = Flask(__name__)

        # Only your own site may call the API from a browser.
    allowed = os.environ.get("ALLOWED_ORIGINS", "https://zalma-frontend.onrender.com")
    origins = [o.strip() for o in allowed.split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins}})

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(preorder_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(rewards_bp)
    app.register_blueprint(badges_bp)
    app.register_blueprint(wall_bp)
    app.register_blueprint(wraps_bp)
    app.register_blueprint(tiers_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(unboxing_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payments_bp)
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=(Config.FLASK_ENV == "development"))
