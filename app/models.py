from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


# Neon/Postgres gets real JSONB (per the handoff spec's data model); the
# SQLite dev fallback gets plain JSON since SQLite has no JSONB type.
JSONB = db.JSON().with_variant(postgresql.JSONB(), "postgresql")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    api_token = db.Column(db.String(128), unique=True, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    active_pantry_id = db.Column(db.Integer, db.ForeignKey("pantries.id"), nullable=True)
    active_pantry = db.relationship("Pantry", foreign_keys=[active_pantry_id], post_update=True)

    recipes = db.relationship(
        "Recipe", back_populates="owner", foreign_keys="Recipe.owner_id", cascade="all, delete-orphan"
    )
    pantries = db.relationship(
        "Pantry", back_populates="owner", foreign_keys="Pantry.owner_id", cascade="all, delete-orphan"
    )
    grocery_lists = db.relationship("GroceryList", back_populates="owner", cascade="all, delete-orphan")


class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="experimental", nullable=False)  # 'experimental' | 'core'
    times_made = db.Column(db.Integer, default=0, nullable=False)
    servings = db.Column(db.Integer, nullable=True)

    source_type = db.Column(db.String(20), nullable=False)  # 'manual' | 'instagram' | 'website'
    source_url = db.Column(db.Text, nullable=True)
    raw_text = db.Column(db.Text, nullable=True)
    raw_image = db.Column(db.LargeBinary, nullable=True)  # screenshot bytes, when that was the source instead
    needs_review = db.Column(db.Boolean, default=False, nullable=False)  # true for async Shortcut imports

    ingredients = db.Column(JSONB, nullable=False, default=list)  # [{name, quantity, unit}]
    steps = db.Column(JSONB, nullable=False, default=list)  # [str, ...]
    tags = db.Column(JSONB, nullable=False, default=list)  # [str, ...]

    shared_from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    shared_from_recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="recipes", foreign_keys=[owner_id])
    notes = db.relationship(
        "RecipeNote",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeNote.created_at.desc()",
    )

    AUTO_PROMOTE_THRESHOLD = 5

    def mark_made(self):
        self.times_made += 1
        if self.times_made >= self.AUTO_PROMOTE_THRESHOLD:
            self.status = "core"


class RecipeNote(db.Model):
    __tablename__ = "recipe_notes"

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    recipe = db.relationship("Recipe", back_populates="notes")


class QuantityEquivalency(db.Model):
    __tablename__ = "quantity_equivalencies"

    id = db.Column(db.Integer, primary_key=True)
    phrase = db.Column(db.String(120), unique=True, nullable=False)  # normalized, e.g. "pinch"
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(60), nullable=False)


class Pantry(db.Model):
    __tablename__ = "pantries"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="pantries", foreign_keys=[owner_id])
    items = db.relationship("PantryItem", back_populates="pantry", cascade="all, delete-orphan")


class PantryItem(db.Model):
    __tablename__ = "pantry_items"

    id = db.Column(db.Integer, primary_key=True)
    pantry_id = db.Column(db.Integer, db.ForeignKey("pantries.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)  # normalized ingredient name
    added_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    pantry = db.relationship("Pantry", back_populates="items")


class GroceryList(db.Model):
    __tablename__ = "grocery_lists"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    pantry_id_used = db.Column(db.Integer, db.ForeignKey("pantries.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="grocery_lists")
    recipes_used = db.relationship(
        "GroceryListRecipe", back_populates="grocery_list", cascade="all, delete-orphan"
    )
    items = db.relationship(
        "GroceryListItem", back_populates="grocery_list", cascade="all, delete-orphan"
    )


class GroceryListRecipe(db.Model):
    __tablename__ = "grocery_list_recipes"

    id = db.Column(db.Integer, primary_key=True)
    grocery_list_id = db.Column(db.Integer, db.ForeignKey("grocery_lists.id"), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False)
    scale = db.Column(db.Float, default=1.0, nullable=False)

    grocery_list = db.relationship("GroceryList", back_populates="recipes_used")
    recipe = db.relationship("Recipe")


class GroceryListItem(db.Model):
    __tablename__ = "grocery_list_items"

    id = db.Column(db.Integer, primary_key=True)
    grocery_list_id = db.Column(db.Integer, db.ForeignKey("grocery_lists.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    # String, not numeric: unresolved vague quantities are stored as plain-
    # multiplier text (e.g. "2x") alongside unit="Conor fix this" — see
    # Quantity equivalencies in the handoff spec.
    quantity = db.Column(db.String(60), nullable=True)
    unit = db.Column(db.String(60), nullable=True)
    source = db.Column(db.String(20), default="recipe", nullable=False)  # 'recipe' | 'manual'
    checked = db.Column(db.Boolean, default=False, nullable=False)

    grocery_list = db.relationship("GroceryList", back_populates="items")
