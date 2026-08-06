from flask import Blueprint, render_template, request, redirect, url_for, g, flash, abort

from app.extensions import db
from app.auth_utils import login_required
from app.models import (
    Recipe,
    Pantry,
    GroceryList,
    GroceryListItem,
    GroceryListRecipe,
    QuantityEquivalency,
)
from app.services.grocery import (
    build_equivalency_lookup,
    expand_recipe_ingredients,
    combine_lines,
    drop_pantry_items,
    merge_lines_into_list,
)

bp = Blueprint("grocery", __name__, url_prefix="/grocery")

MAX_RECIPES_PER_LIST = 4


def _active_pantry_names():
    if not g.user.active_pantry_id:
        return set()
    pantry = Pantry.query.get(g.user.active_pantry_id)
    if pantry is None:
        return set()
    return {item.name for item in pantry.items}


def _get_or_create_current_list():
    current = (
        GroceryList.query.filter_by(owner_id=g.user.id)
        .order_by(GroceryList.created_at.desc())
        .first()
    )
    if current is None:
        current = GroceryList(owner_id=g.user.id, pantry_id_used=g.user.active_pantry_id)
        db.session.add(current)
        db.session.commit()
    return current


def _get_visible_recipe(recipe_id):
    """A recipe page's "Add to grocery list" action, and What-can-I-make
    results, can reference either the user's own recipe (any status) or a
    friend's core recipe (per the Friends visibility rule)."""
    recipe = Recipe.query.filter_by(id=recipe_id).first_or_404()
    if recipe.owner_id == g.user.id:
        return recipe
    if recipe.status == "core":
        return recipe
    return abort(404)


@bp.route("")
@login_required
def current_list():
    current = (
        GroceryList.query.filter_by(owner_id=g.user.id)
        .order_by(GroceryList.created_at.desc())
        .first()
    )
    return render_template("grocery/current.html", grocery_list=current)


@bp.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    recipes = Recipe.query.filter_by(owner_id=g.user.id).order_by(Recipe.title).all()

    if request.method == "POST":
        selected_ids = [int(i) for i in request.form.getlist("recipe_ids") if i.isdigit()]
        if not selected_ids:
            return render_template("grocery/generate.html", recipes=recipes, error="Pick at least one recipe.")
        if len(selected_ids) > MAX_RECIPES_PER_LIST:
            return render_template(
                "grocery/generate.html", recipes=recipes, error=f"Pick at most {MAX_RECIPES_PER_LIST} recipes."
            )

        selected_recipes = Recipe.query.filter(
            Recipe.id.in_(selected_ids), Recipe.owner_id == g.user.id
        ).all()

        scale_by_recipe = {}
        for recipe in selected_recipes:
            raw = request.form.get(f"scale_{recipe.id}", "").strip()
            if recipe.servings:
                desired = float(raw) if raw else float(recipe.servings)
                scale_by_recipe[recipe.id] = desired / recipe.servings
            else:
                scale_by_recipe[recipe.id] = float(raw) if raw else 1.0

        equivalencies = build_equivalency_lookup(QuantityEquivalency.query.all())
        all_lines = []
        for recipe in selected_recipes:
            all_lines.extend(expand_recipe_ingredients(recipe, scale_by_recipe[recipe.id], equivalencies))

        combined = combine_lines(all_lines)
        pantry_id_used = g.user.active_pantry_id
        combined = drop_pantry_items(combined, _active_pantry_names())

        return render_template(
            "grocery/generate_review.html",
            items=combined,
            selected_recipes=[(r, scale_by_recipe[r.id]) for r in selected_recipes],
            pantry_id_used=pantry_id_used or "",
        )

    return render_template("grocery/generate.html", recipes=recipes)


@bp.route("/generate/confirm", methods=["POST"])
@login_required
def generate_confirm():
    names = request.form.getlist("item_name")
    quantities = request.form.getlist("item_quantity")
    units = request.form.getlist("item_unit")
    skip_indexes = {int(i) for i in request.form.getlist("skip") if i.isdigit()}

    recipe_ids = request.form.getlist("recipe_id")
    scales = request.form.getlist("scale_value")
    pantry_id_used = request.form.get("pantry_id_used") or None

    grocery_list = GroceryList(
        owner_id=g.user.id,
        pantry_id_used=int(pantry_id_used) if pantry_id_used else None,
    )
    db.session.add(grocery_list)
    db.session.flush()

    for rid, scale in zip(recipe_ids, scales):
        recipe = Recipe.query.filter_by(id=int(rid), owner_id=g.user.id).first()
        if recipe is None:
            continue
        db.session.add(
            GroceryListRecipe(grocery_list_id=grocery_list.id, recipe_id=recipe.id, scale=float(scale))
        )

    for i, (name, quantity, unit) in enumerate(zip(names, quantities, units)):
        if i in skip_indexes:
            continue
        db.session.add(
            GroceryListItem(
                grocery_list_id=grocery_list.id,
                name=name,
                quantity=quantity or None,
                unit=unit or None,
                source="recipe",
                checked=False,
            )
        )

    db.session.commit()
    return redirect(url_for("grocery.current_list"))


@bp.route("/manual-item", methods=["POST"])
@login_required
def add_manual_item():
    name = request.form.get("name", "").strip()
    if name:
        current = _get_or_create_current_list()
        db.session.add(
            GroceryListItem(grocery_list_id=current.id, name=name, source="manual", checked=False)
        )
        db.session.commit()
    return redirect(url_for("grocery.current_list"))


@bp.route("/items/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_item(item_id):
    item = (
        GroceryListItem.query.join(GroceryList)
        .filter(GroceryListItem.id == item_id, GroceryList.owner_id == g.user.id)
        .first_or_404()
    )
    item.checked = not item.checked
    db.session.commit()
    return redirect(url_for("grocery.current_list"))


@bp.route("/add-recipe/<int:recipe_id>", methods=["POST"])
@login_required
def add_recipe_to_current(recipe_id):
    recipe = _get_visible_recipe(recipe_id)
    scale_raw = request.form.get("scale", "").strip()
    scale = float(scale_raw) if scale_raw else 1.0

    equivalencies = build_equivalency_lookup(QuantityEquivalency.query.all())
    lines = expand_recipe_ingredients(recipe, scale, equivalencies)

    current = _get_or_create_current_list()
    merge_lines_into_list(current, lines, _active_pantry_names())
    db.session.commit()

    flash(f'Added "{recipe.title}" to your grocery list.')
    return redirect(request.referrer or url_for("grocery.current_list"))
