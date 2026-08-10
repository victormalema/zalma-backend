from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from routes.auth_routes import auth_bp
from routes.products_routes import products_bp
from routes.cart_routes import cart_bp
from routes.wishlist_routes import wishlist_bp
from routes.orders_routes import orders_bp
from routes.rewards_routes import rewards_bp
from routes.badges_routes import badges_bp
from routes.wall_routes import wall_bp


def create_app():
    Config.validate()

    app = Flask(__name__)

    # Allow requests from your frontend. Tighten origins before going
    # to production -- right now this allows any origin.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(wishlist_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(rewards_bp)
    app.register_blueprint(badges_bp)
    app.register_blueprint(wall_bp)

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
