"""Removes the old demo user (and its 3 dummy recipes) and seeds Conor's
real recipes, parsed from RecipesConor, for the "conor" user.

These recipes are ingredients-only by design — no steps.

Run with: python seed_conor.py
Log in as username "conor" afterward (no password needed).
"""

from app import create_app
from app.extensions import db
from app.models import Recipe, User

CONOR_RECIPES = [
    {
        "title": "Shrimp Scampi",
        "servings": 6,
        "source_type": "manual",
        "ingredients": [
            {"name": "shrimp", "quantity": "2", "unit": "lb"},
            {"name": "pasta", "quantity": "1", "unit": "lb"},
            {"name": "olive oil", "quantity": "", "unit": ""},
            {"name": "cherry tomatoes", "quantity": "1", "unit": "pack"},
            {"name": "onions", "quantity": "2", "unit": "whole"},
            {"name": "garlic cloves", "quantity": "10", "unit": "cloves"},
            {"name": "white wine", "quantity": "2", "unit": "small bottles"},
            {"name": "lemon juice", "quantity": "", "unit": ""},
        ],
        "steps": [],
        "tags": [],
    },
    {
        "title": "Beef Stew",
        "servings": 6,
        "source_type": "manual",
        "ingredients": [
            {"name": "beef chuck, cut into 1.5-2 inch chunks", "quantity": "2.5", "unit": "lb"},
            {"name": "flour", "quantity": "2-3", "unit": "tbsp"},
            {"name": "olive oil", "quantity": "2", "unit": "tbsp"},
            {"name": "yellow onion, roughly chopped", "quantity": "2", "unit": "large"},
            {"name": "garlic, minced", "quantity": "10", "unit": "cloves"},
            {"name": "tomato paste", "quantity": "2", "unit": "tbsp"},
            {"name": "dry red wine", "quantity": "1", "unit": "cup"},
            {"name": "beef stock", "quantity": "1", "unit": "carton"},
            {"name": "bay leaves", "quantity": "2", "unit": "whole"},
            {"name": "carrots, cut into large pieces", "quantity": "4", "unit": "medium"},
            {"name": "celery", "quantity": "4", "unit": "stalks"},
            {"name": "Yukon Gold potatoes, cut into large chunks", "quantity": "1.5", "unit": "lb"},
            {"name": "frozen peas", "quantity": "1", "unit": "bag"},
        ],
        "steps": [],
        "tags": [],
    },
    {
        "title": "Chicken with Spices",
        "servings": 8,
        "source_type": "manual",
        "ingredients": [
            {"name": "chicken", "quantity": "3.5", "unit": "lbs"},
            {"name": "potatoes", "quantity": "1", "unit": "bag"},
            {"name": "asparagus (1 bunch) or broccoli (2 heads)", "quantity": "", "unit": ""},
        ],
        "steps": [],
        "tags": [],
    },
    {
        "title": "Orzo Salad",
        "servings": 6,
        "source_type": "manual",
        "ingredients": [
            {"name": "orzo", "quantity": "0.5", "unit": "box"},
            {"name": "cucumbers", "quantity": "4", "unit": "small"},
            {"name": "chickpeas", "quantity": "2", "unit": "cans"},
            {"name": "red onion (pickled)", "quantity": "1", "unit": "whole"},
            {"name": "feta cheese", "quantity": "", "unit": ""},
            {"name": "balsamic vinegar", "quantity": "", "unit": ""},
            {"name": "olive oil", "quantity": "", "unit": ""},
            {"name": "lemon juice", "quantity": "", "unit": ""},
            {"name": "cherry tomatoes", "quantity": "2", "unit": "packages"},
        ],
        "steps": [],
        "tags": [],
    },
    {
        "title": "Tacos",
        "servings": 4,
        "source_type": "manual",
        "ingredients": [
            {"name": "ground beef", "quantity": "1", "unit": "lb"},
            {"name": "onion", "quantity": "1", "unit": "whole"},
            {"name": "taco seasoning", "quantity": "", "unit": ""},
            {"name": "cherry tomatoes", "quantity": "1", "unit": "package"},
            {"name": "avocado", "quantity": "1", "unit": "whole"},
            {"name": "tortillas", "quantity": "1", "unit": "pack"},
            {"name": "beans", "quantity": "1", "unit": "can"},
            {"name": "cheese", "quantity": "1", "unit": "pack"},
            {"name": "sour cream", "quantity": "1", "unit": ""},
        ],
        "steps": [],
        "tags": [],
    },
    {
        "title": "Spaghetti",
        "servings": 4,
        "source_type": "manual",
        "ingredients": [
            {"name": "ground beef", "quantity": "1", "unit": "lb"},
            {"name": "marinara", "quantity": "1", "unit": "jar"},
            {"name": "onion", "quantity": "1", "unit": "whole"},
            {"name": "garlic cloves", "quantity": "5", "unit": "cloves"},
            {"name": "pasta", "quantity": "1", "unit": "lb"},
        ],
        "steps": [],
        "tags": [],
    },
]


def seed():
    app = create_app()
    with app.app_context():
        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is not None:
            db.session.delete(demo_user)  # cascades to its recipes/pantries/grocery lists
            db.session.commit()
            print("Removed demo user and its dummy recipes.")

        user = User.query.filter_by(username="conor").first()
        if user is None:
            user = User(username="conor")
            db.session.add(user)
            db.session.flush()

        existing_titles = {r.title for r in user.recipes}
        added = 0
        for data in CONOR_RECIPES:
            if data["title"] in existing_titles:
                continue
            recipe = Recipe(owner_id=user.id, **data)
            db.session.add(recipe)
            added += 1

        db.session.commit()
        print(f"Seeded {added} recipe(s) for user 'conor' (total now: {len(user.recipes)}).")


if __name__ == "__main__":
    seed()
