from flask import Blueprint, request, jsonify
from services.products_service import (
    get_all_collections,
    get_products,
    get_product_by_slug,
    ProductError,
)

products_bp = Blueprint("products", __name__, url_prefix="/api")


@products_bp.route("/collections", methods=["GET"])
def list_collections():
    collections = get_all_collections()
    return jsonify({"collections": collections}), 200


@products_bp.route("/products", methods=["GET"])
def list_products():
    collection_slug = request.args.get("collection")
    try:
        products = get_products(collection_slug=collection_slug)
        return jsonify({"products": products}), 200
    except ProductError as e:
        return jsonify({"error": e.message}), e.status_code


@products_bp.route("/products/<slug>", methods=["GET"])
def product_detail(slug):
    try:
        product = get_product_by_slug(slug)
        return jsonify({"product": product}), 200
    except ProductError as e:
        return jsonify({"error": e.message}), e.status_code