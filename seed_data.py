"""
Populates a couple of sample collections and products so the frontend
has real data to hit once product endpoints exist.

Run with: python seed_data.py
Safe to re-run -- it checks for existing slugs before inserting.
"""

from database.supabase_client import get_supabase

COLLECTIONS = [
    {
        "name": "A New Chapter",
        "slug": "a-new-chapter",
        "description": "The debut ZALMA collection.",
        "cover_image": "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=1200&q=80",
    },
    {
        "name": "Wall Culture Capsule",
        "slug": "wall-culture-capsule",
        "description": "Limited streetwear-inspired capsule.",
        "cover_image": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=1200&q=80",
    },
]

PRODUCTS = [
    {
        "collection_slug": "a-new-chapter",
        "name": "Ivory Tailored Coat",
        "slug": "ivory-tailored-coat",
        "price": 8500.00,
        "description": "Structured wool-blend coat in ivory.",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Ivory", "Black"],
        "images": ["https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=800&q=80"],
        "stock": 25,
    },
    {
        "collection_slug": "wall-culture-capsule",
        "name": "Bronze Graphic Tee",
        "slug": "bronze-graphic-tee",
        "price": 2200.00,
        "description": "Heavyweight cotton tee with bronze foil print.",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "colors": ["Black", "Ivory"],
        "images": ["https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80"],
        "stock": 60,
    },
]


def seed():
    supabase = get_supabase()

    collection_ids = {}
    for c in COLLECTIONS:
        existing = supabase.table("collections").select("id").eq("slug", c["slug"]).execute()
        if existing.data:
            collection_ids[c["slug"]] = existing.data[0]["id"]
            print(f"Skipping existing collection: {c['slug']}")
            continue
        result = supabase.table("collections").insert(c).execute()
        collection_ids[c["slug"]] = result.data[0]["id"]
        print(f"Created collection: {c['slug']}")

    for p in PRODUCTS:
        existing = supabase.table("products").select("id").eq("slug", p["slug"]).execute()
        if existing.data:
            print(f"Skipping existing product: {p['slug']}")
            continue
        payload = {k: v for k, v in p.items() if k != "collection_slug"}
        payload["collection_id"] = collection_ids[p["collection_slug"]]
        supabase.table("products").insert(payload).execute()
        print(f"Created product: {p['slug']}")

    print("Done.")


if __name__ == "__main__":
    seed()
