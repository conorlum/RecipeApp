import re

from flask import Blueprint, render_template, request, g

from app.auth_utils import login_required
from app.models import Recipe, Pantry
from app.services.matching import rank_recipes

bp = Blueprint("what_can_i_make", __name__)

_SPLIT_RE = re.compile(r"[\n,]+")


def _split_ingredients(text):
    return [t.strip() for t in _SPLIT_RE.split(text or "") if t.strip()]


def _pantry_ingredients_text():
    if not g.user.active_pantry_id:
        return ""
    pantry = Pantry.query.get(g.user.active_pantry_id)
    if pantry is None:
        return ""
    return "\n".join(item.name for item in pantry.items)


@bp.route("/what-can-i-make", methods=["GET", "POST"])
@login_required
def search():
    if request.method == "POST":
        ingredients_text = request.form.get("ingredients", "")
        toggles = {
            "core": "core" in request.form,
            "experimental": "experimental" in request.form,
            "friends": "friends" in request.form,
            "internet": False,  # v2 — deferred, needs real search integration
        }
    else:
        ingredients_text = _pantry_ingredients_text()
        toggles = {"core": True, "experimental": True, "friends": False, "internet": False}

    results = []
    if request.method == "POST":
        have_ingredients = _split_ingredients(ingredients_text)

        pool = []
        labels = {}
        if toggles["core"]:
            for r in Recipe.query.filter_by(owner_id=g.user.id, status="core").all():
                pool.append(r)
                labels[r.id] = "yours"
        if toggles["experimental"]:
            for r in Recipe.query.filter_by(owner_id=g.user.id, status="experimental").all():
                pool.append(r)
                labels[r.id] = "yours"
        if toggles["friends"]:
            for r in Recipe.query.filter(Recipe.owner_id != g.user.id, Recipe.status == "core").all():
                pool.append(r)
                labels[r.id] = f"from @{r.owner.username}"

        ranked = rank_recipes(pool, have_ingredients)
        results = [
            {"recipe": r, "label": labels[r.id], **score}
            for r, score in ranked
            if score["total"] > 0
        ]

    return render_template(
        "what_can_i_make/search.html",
        ingredients_text=ingredients_text,
        toggles=toggles,
        results=results,
        searched=request.method == "POST",
    )
