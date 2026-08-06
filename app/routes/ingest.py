import base64

from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify

from app.extensions import db
from app.auth_utils import login_required, token_required
from app.models import Recipe
from app.services.parsing import (
    import_from_website,
    import_from_instagram,
    fetch_instagram_caption,
    parse_recipe_with_claude,
    parse_recipe_image_with_claude,
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


def _render_review(
    source_type, source_url, raw_text=None, parsed=None, error=None, raw_image_b64=None, media_type=None
):
    return render_template(
        "ingest/review.html",
        source_type=source_type,
        source_url=source_url or "",
        raw_text=raw_text,
        raw_image_b64=raw_image_b64,
        media_type=media_type or "image/jpeg",
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


@bp.route("/recipes/import/screenshot", methods=["GET", "POST"])
@login_required
def import_screenshot():
    if request.method == "POST":
        image_file = request.files.get("image")
        source_url = request.form.get("source_url", "").strip()
        if not image_file or not image_file.filename:
            return render_template("ingest/screenshot_form.html", error="Choose a screenshot to upload.")

        image_bytes = image_file.read()
        media_type = image_file.mimetype or "image/jpeg"
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        parsed = parse_recipe_image_with_claude(image_bytes, media_type)

        if "error" in parsed:
            return _render_review(
                "instagram", source_url, error=parsed["error"], raw_image_b64=image_b64, media_type=media_type
            )
        return _render_review("instagram", source_url, parsed=parsed, raw_image_b64=image_b64, media_type=media_type)

    return render_template("ingest/screenshot_form.html")


@bp.route("/recipes/import/reparse-image", methods=["POST"])
@login_required
def reparse_image_from_raw():
    """Re-parse the same uploaded screenshot bytes, used by the review
    screen's "Re-parse from this screenshot" button for another attempt."""
    source_type = request.form.get("source_type", "instagram")
    source_url = request.form.get("source_url", "").strip()
    image_b64 = request.form.get("raw_image_b64", "")
    media_type = request.form.get("media_type", "image/jpeg")

    if not image_b64:
        return _render_review(source_type, source_url, error="No image to re-parse.")

    image_bytes = base64.b64decode(image_b64)
    parsed = parse_recipe_image_with_claude(image_bytes, media_type)
    if "error" in parsed:
        return _render_review(
            source_type, source_url, error=parsed["error"], raw_image_b64=image_b64, media_type=media_type
        )
    return _render_review(source_type, source_url, parsed=parsed, raw_image_b64=image_b64, media_type=media_type)


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
    raw_text = request.form.get("raw_text", "").strip() or None
    raw_image_b64 = request.form.get("raw_image_b64", "")
    servings = request.form.get("servings", "").strip()

    if not title:
        return _render_review(
            source_type,
            source_url,
            raw_text,
            error="Title is required before saving.",
            raw_image_b64=raw_image_b64 or None,
            media_type=request.form.get("media_type"),
        )

    recipe = Recipe(
        owner_id=g.user.id,
        title=title,
        source_type=source_type,
        source_url=source_url,
        raw_text=raw_text,
        raw_image=base64.b64decode(raw_image_b64) if raw_image_b64 else None,
        ingredients=[parse_ingredient_line(line) for line in _split_lines(request.form.get("ingredients"))],
        steps=_split_lines(request.form.get("steps")),
        tags=_split_tags(request.form.get("tags")),
        servings=int(servings) if servings.isdigit() else None,
    )
    db.session.add(recipe)
    db.session.commit()
    return redirect(url_for("recipes.detail", recipe_id=recipe.id))


@bp.route("/api/ingest", methods=["POST"])
@token_required
def api_ingest():
    """Instagram ingestion path 1 — the Shortcut share-sheet endpoint.
    Authenticated via api_token bearer header (see token_required), not a
    session cookie, since there's no browser session when a Shortcut fires.

    POST {"url": "..."} -> tries to fetch+parse the post's public caption;
    if that fails (private account, blocked fetch, or Claude can't find a
    recipe in what it found), saves a stub instead of failing the request.
    Either way the recipe is saved immediately with needs_review=True, since
    nobody was looking at a screen to confirm it — no review-before-save
    step here, unlike the paste-text/screenshot paths."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required."}), 400

    caption = fetch_instagram_caption(url)
    parsed = parse_recipe_with_claude(caption) if caption else None

    if parsed and "error" not in parsed:
        title = parsed.get("title") or "New Instagram recipe"
        ingredients = parsed.get("ingredients") or []
        steps = parsed.get("steps") or []
        servings = parsed.get("servings")
    else:
        title = "New Instagram recipe"
        ingredients = []
        steps = []
        servings = None

    recipe = Recipe(
        owner_id=g.user.id,
        title=title,
        source_type="instagram",
        source_url=url,
        raw_text=caption,
        ingredients=ingredients,
        steps=steps,
        tags=[],
        servings=servings,
        needs_review=True,
    )
    db.session.add(recipe)
    db.session.commit()
    return jsonify({"id": recipe.id, "title": recipe.title}), 201
