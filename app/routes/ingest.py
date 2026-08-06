from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify

from app.extensions import db
from app.auth_utils import login_required
from app.models import Recipe
from app.services.parsing import (
    import_from_website,
    import_from_instagram,
    parse_recipe_with_claude,
    parse_ingredient_line,
)

bp = Blueprint("ingest", __name__)


def _split_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _split_tags(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _ingredients_to_text(ingredients):
    lines = []
    for ing in ingredients or []:
        parts = [str(ing.get("quantity") or ""), str(ing.get("unit") or ""), str(ing.get("name") or "")]
        lines.append(" ".join(p for p in parts if p).strip())
    return "\n".join(lines)


def _render_review(source_type, source_url, raw_text, parsed=None, error=None):
    return render_template(
        "ingest/review.html",
        source_type=source_type,
        source_url=source_url or "",
        raw_text=raw_text,
        parsed=parsed,
        error=error,
        ingredients_text=_ingredients_to_text(parsed["ingredients"]) if parsed else "",
        steps_text="\n".join(parsed["steps"]) if parsed else "",
    )


@bp.route("/recipes/import/website", methods=["GET", "POST"])
@login_required
def import_website():
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            return render_template("ingest/website_form.html", error="A URL is required.")

        try:
            parsed, raw_text = import_from_website(url)
        except Exception:
            return render_template(
                "ingest/website_form.html",
                error="Couldn't fetch that URL. Check it and try again.",
                url=url,
            )

        if "error" in parsed:
            return _render_review("website", url, raw_text, error=parsed["error"])
        return _render_review("website", url, raw_text, parsed=parsed)

    return render_template("ingest/website_form.html")


@bp.route("/recipes/import/instagram", methods=["GET", "POST"])
@login_required
def import_instagram():
    if request.method == "POST":
        raw_text = request.form.get("raw_text", "").strip()
        source_url = request.form.get("source_url", "").strip()
        if not raw_text:
            return render_template("ingest/instagram_form.html", error="Paste the caption text first.")

        parsed, raw_text = import_from_instagram(raw_text)
        if "error" in parsed:
            return _render_review("instagram", source_url, raw_text, error=parsed["error"])
        return _render_review("instagram", source_url, raw_text, parsed=parsed)

    return render_template("ingest/instagram_form.html")


@bp.route("/recipes/import/parse", methods=["POST"])
@login_required
def reparse_from_raw():
    """Re-parse (or first parse) directly from raw_text, used by the review
    screen's "Re-parse from raw text" button after the user tweaks wording."""
    source_type = request.form.get("source_type", "website")
    source_url = request.form.get("source_url", "").strip()
    raw_text = request.form.get("raw_text", "").strip()

    if not raw_text:
        return _render_review(source_type, source_url, raw_text, error="No text to parse.")

    parsed = parse_recipe_with_claude(raw_text)
    if "error" in parsed:
        return _render_review(source_type, source_url, raw_text, error=parsed["error"])
    return _render_review(source_type, source_url, raw_text, parsed=parsed)


@bp.route("/recipes/import/save", methods=["POST"])
@login_required
def save_import():
    title = request.form.get("title", "").strip()
    source_type = request.form.get("source_type", "website")
    source_url = request.form.get("source_url", "").strip() or None
    raw_text = request.form.get("raw_text", "")
    servings = request.form.get("servings", "").strip()

    if not title:
        return _render_review(
            source_type,
            source_url,
            raw_text,
            error="Title is required before saving.",
        )

    recipe = Recipe(
        owner_id=g.user.id,
        title=title,
        source_type=source_type,
        source_url=source_url,
        raw_text=raw_text,
        ingredients=[parse_ingredient_line(line) for line in _split_lines(request.form.get("ingredients"))],
        steps=_split_lines(request.form.get("steps")),
        tags=_split_tags(request.form.get("tags")),
        servings=int(servings) if servings.isdigit() else None,
    )
    db.session.add(recipe)
    db.session.commit()
    return redirect(url_for("recipes.detail", recipe_id=recipe.id))


@bp.route("/api/ingest", methods=["POST"])
@login_required
def api_ingest():
    """POST {source_type, raw_text, source_url?} -> Claude-parsed recipe
    fields (or {"error": "..."}). Parsing only — saving happens through the
    review-before-save screen, not this endpoint."""
    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()
    if not raw_text:
        return jsonify({"error": "raw_text is required."}), 400

    result = parse_recipe_with_claude(raw_text)
    return jsonify(result)
