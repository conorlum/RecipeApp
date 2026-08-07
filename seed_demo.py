"""One-off script to seed a demo user with 3 sample recipes.

Run with: python seed_demo.py
Log in as username "demo" afterward (no password needed).
"""

from app import create_app
from app.extensions import db
from app.models import Recipe, User

DEMO_RECIPES = [
    {
        "title": "Weeknight Garlic Butter Pasta",
        "status": "core",
        "times_made": 6,
        "servings": 4,
        "source_type": "manual",
        "ingredients": [
            {"name": "spaghetti", "quantity": "1", "unit": "lb"},
            {"name": "butter", "quantity": "4", "unit": "tbsp"},
            {"name": "garlic", "quantity": "6", "unit": "cloves"},
            {"name": "parmesan", "quantity": "1", "unit": "cup"},
            {"name": "red pepper flakes", "quantity": "0.5", "unit": "tsp"},
        ],
        "steps": [
            "Boil pasta in salted water until al dente, reserving 1 cup of pasta water.",
            "Melt butter in a large skillet and saute minced garlic until fragrant.",
            "Toss in the drained pasta, parmesan, and a splash of pasta water until glossy.",
            "Finish with red pepper flakes and serve immediately.",
        ],
        "tags": ["pasta", "quick", "vegetarian"],
    },
    {
        "title": "Sheet Pan Lemon Herb Chicken",
        "status": "experimental",
        "times_made": 1,
        "servings": 4,
        "source_type": "website",
        "source_url": "https://example.com/lemon-herb-chicken",
        "ingredients": [
            {"name": "chicken thighs", "quantity": "8", "unit": "pieces"},
            {"name": "baby potatoes", "quantity": "1.5", "unit": "lb"},
            {"name": "lemon", "quantity": "2", "unit": "whole"},
            {"name": "olive oil", "quantity": "3", "unit": "tbsp"},
            {"name": "rosemary", "quantity": "2", "unit": "sprigs"},
        ],
        "steps": [
            "Preheat oven to 425F.",
            "Toss potatoes and chicken with olive oil, lemon juice, and rosemary on a sheet pan.",
            "Roast for 35-40 minutes until chicken is golden and potatoes are tender.",
            "Squeeze remaining lemon over the top before serving.",
        ],
        "tags": ["chicken", "sheet-pan", "dinner"],
    },
    {
        "title": "Instagram Reel Smash Burgers",
        "status": "experimental",
        "times_made": 0,
        "servings": 2,
        "source_type": "instagram",
        "source_url": "https://instagram.com/reel/example",
        "needs_review": True,
        "ingredients": [
            {"name": "ground beef", "quantity": "0.5", "unit": "lb"},
            {"name": "american cheese", "quantity": "2", "unit": "slices"},
            {"name": "burger buns", "quantity": "2", "unit": "whole"},
            {"name": "onion", "quantity": "0.5", "unit": "whole"},
        ],
        "steps": [
            "Form beef into loose balls, season with salt and pepper.",
            "Smash onto a hot griddle with thinly sliced onion underneath.",
            "Flip once, top with cheese, and melt.",
            "Stack on toasted buns with your favorite condiments.",
        ],
        "tags": ["burgers", "beef", "quick"],
    },
]


def seed():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username="demo").first()
        if user is None:
            user = User(username="demo")
            db.session.add(user)
            db.session.flush()

        existing_titles = {r.title for r in user.recipes}
        added = 0
        for data in DEMO_RECIPES:
            if data["title"] in existing_titles:
                continue
            recipe = Recipe(owner_id=user.id, **data)
            db.session.add(recipe)
            added += 1

        db.session.commit()
        print(f"Seeded {added} demo recipe(s) for user 'demo' (total now: {len(user.recipes)}).")


if __name__ == "__main__":
    seed()
