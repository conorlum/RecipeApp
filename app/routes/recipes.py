from flask import Blueprint, render_template, request, redirect, url_for, g, flash, Response, abort

from app.extensions import db
from app.auth_utils import login_required
from app.models import User, Recipe, RecipeNote
from app.services.parsing import parse_ingredient_line, parse_recipe_with_claude, parse_recipe_image_with_claude

bp = Blueprint("recipes", __name__, url_prefix="/recipes")


def _split_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _split_tags(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _get_owned_recipe(recipe_id):
    return Recipe.query.filter_by(id=recipe_id, owner_id=g.user.id).first_or_404()


@bp.route("")
@login_required
def list_recipes():
    query = Recipe.query.filter_by(owner_id=g.user.id)
    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(Recipe.title.ilike(f"%{q}%"))
    recipes = query.order_by(Recipe.created_at.desc()).all()
    return render_template("recipes/list.html", recipes=recipes, q=q)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_recipe():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            return render_template("recipes/new.html", error="Title is required.", form=request.form)

        ingredients = [parse_ingredient_line(line) for line in _split_lines(request.form.get("ingredients"))]
        steps = _split_lines(request.form.get("steps"))
        tags = _split_tags(request.form.get("tags"))
        servings = request.form.get("servings", "").strip()

        recipe = Recipe(
            owner_id=g.user.id,
            title=title,
            source_type="manual",
            ingredients=ingredients,
            steps=steps,
            tags=tags,
            servings=int(servings) if servings.isdigit() else None,
        )
        db.session.add(recipe)
        db.session.commit()
        return redirect(url_for("recipes.detail", recipe_id=recipe.id))

    return render_template("recipes/new.html")


@bp.route("/<int:recipe_id>")
@login_required
def detail(recipe_id):
    recipe = _get_owned_recipe(recipe_id)
    return render_template("recipes/detail.html", recipe=recipe)


@bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit(recipe_id):
    recipe = _get_owned_recipe(recipe_id)

    if request.method == "POST":
        recipe.title = request.form.get("title", "").strip() or recipe.title
        recipe.ingredients = [
            parse_ingredient_line(line) for line in _split_lines(request.form.get("ingredients"))
        ]
        recipe.steps = _split_lines(request.form.get("steps"))
        recipe.tags = _split_tags(request.form.get("tags"))
        servings = request.form.get("servings", "").strip()
        recipe.servings = int(servings) if servings.isdigit() else None
        # Cleared the first time the recipe is opened and saved/confirmed —
        # not just opened (see handoff: needs_review).
        recipe.needs_review = False
        db.session.commit()
        return redirect(url_for("recipes.detail", recipe_id=recipe.id))

    return render_template("recipes/edit.html", recipe=recipe)


@bp.route("/<int:recipe_id>/reparse", methods=["POST"])
@login_required
def reparse(recipe_id):
    recipe = _get_owned_recipe(recipe_id)
    raw_text = request.form.get("raw_text", "").strip() or recipe.raw_text
    if not raw_text:
        flash("No raw text to re-parse from.")
        return redirect(url_for("recipes.edit", recipe_id=recipe.id))

    # Persist the (possibly tweaked) wording either way — raw_text is kept
    # permanently as the source of truth for future fixes.
    recipe.raw_text = raw_text
    db.session.commit()

    result = parse_recipe_with_claude(raw_text)
    if "error" in result:
        return render_template("recipes/edit.html", recipe=recipe, parse_error=result["error"])

    return render_template("recipes/edit.html", recipe=recipe, reparsed=result)


@bp.route("/<int:recipe_id>/reparse-image", methods=["POST"])
@login_required
def reparse_image(recipe_id):
    """Screenshot-upload counterpart to reparse() — how a needs_review stub
    (or any recipe) gets finished via path 3 of Instagram ingestion."""
    recipe = _get_owned_recipe(recipe_id)
    image_file = request.files.get("image")
    if not image_file or not image_file.filename:
        flash("Choose a screenshot to upload.")
        return redirect(url_for("recipes.edit", recipe_id=recipe.id))

    image_bytes = image_file.read()
    media_type = image_file.mimetype or "image/jpeg"
    # Persisted immediately either way — raw_image is kept permanently as
    # the source of truth for future fixes, same as raw_text.
    recipe.raw_image = image_bytes
    db.session.commit()

    result = parse_recipe_image_with_claude(image_bytes, media_type)
    if "error" in result:
        return render_template("recipes/edit.html", recipe=recipe, parse_error=result["error"])

    return render_template("recipes/edit.html", recipe=recipe, reparsed=result)


@bp.route("/<int:recipe_id>/raw-image")
@login_required
def raw_image(recipe_id):
    recipe = _get_owned_recipe(recipe_id)
    if not recipe.raw_image:
        abort(404)
    return Response(recipe.raw_image, mimetype="image/jpeg")


@bp.route("/<int:recipe_id>/notes", methods=["POST"])
@login_required
def add_note(recipe_id):
    recipe = _get_owned_recipe(recipe_id)
    note_text = request.form.get("note_text", "").strip()
    if note_text:
        db.session.add(RecipeNote(recipe_id=recipe.id, owner_id=g.user.id, note_text=note_text))
        db.session.commit()
    return redirect(url_for("recipes.detail", recipe_id=recipe.id))


@bp.route("/<int:recipe_id>/made", methods=["POST"])
@login_required
def mark_made(recipe_id):
    recipe = _get_owned_recipe(recipe_id)
    recipe.mark_made()
    db.session.commit()
    return redirect(url_for("recipes.detail", recipe_id=recipe.id))


@bp.route("/<int:recipe_id>/mark-core", methods=["POST"])
@login_required
def mark_core(recipe_id):
    recipe = _get_owned_recipe(recipe_id)
    recipe.status = "core"
    db.session.commit()
    return redirect(url_for("recipes.detail", recipe_id=recipe.id))


@bp.route("/<int:recipe_id>/delete", methods=["GET", "POST"])
@login_required
def delete(recipe_id):
    recipe = _get_owned_recipe(recipe_id)

    if request.method == "POST":
        db.session.delete(recipe)
        db.session.commit()
        return redirect(url_for("recipes.list_recipes"))

    return render_template("recipes/delete_confirm.html", recipe=recipe)


@bp.route("/<int:recipe_id>/share", methods=["GET", "POST"])
@login_required
def share(recipe_id):
    recipe = _get_owned_recipe(recipe_id)
    friends = User.query.filter(User.id != g.user.id).order_by(User.username).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        friend = User.query.filter_by(username=username).first()
        if friend is None:
            return render_template("recipes/share.html", recipe=recipe, friends=friends, error="No such user.")

        copy = Recipe(
            owner_id=friend.id,
            title=recipe.title,
            status="experimental",
            times_made=0,
            servings=recipe.servings,
            source_type=recipe.source_type,
            source_url=recipe.source_url,
            raw_text=recipe.raw_text,
            ingredients=recipe.ingredients,
            steps=recipe.steps,
            tags=recipe.tags,
            shared_from_user_id=g.user.id,
            shared_from_recipe_id=recipe.id,
        )
        db.session.add(copy)
        db.session.flush()

        for note in sorted(recipe.notes, key=lambda n: n.created_at):
            db.session.add(RecipeNote(recipe_id=copy.id, owner_id=friend.id, note_text=note.note_text))

        db.session.commit()
        flash(f"Shared \"{recipe.title}\" with {friend.username}.")
        return redirect(url_for("recipes.detail", recipe_id=recipe.id))

    return render_template("recipes/share.html", recipe=recipe, friends=friends)
