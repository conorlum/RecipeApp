from app.services.normalize import normalize_name


def score_recipe(recipe, have_set):
    """Ingredient matching (v1): score = matched / total, names-only.
    Quantities are stored but not used in scoring — see the handoff spec's
    "Ingredient matching" section."""
    names = [normalize_name(ing.get("name", "")) for ing in recipe.ingredients or []]
    names = [n for n in names if n]
    total = len(names)
    if total == 0:
        return {"score": 0.0, "matched": 0, "total": 0, "missing": []}

    missing = [n for n in names if n not in have_set]
    matched = total - len(missing)
    return {"score": matched / total, "matched": matched, "total": total, "missing": missing}


def rank_recipes(recipes, have_ingredients):
    """Score + sort a pool of recipes against a set of ingredients on hand.
    Returns a list of (recipe, score_dict) sorted by score descending."""
    have_set = {normalize_name(x) for x in have_ingredients if normalize_name(x)}
    scored = [(recipe, score_recipe(recipe, have_set)) for recipe in recipes]
    scored.sort(key=lambda pair: pair[1]["score"], reverse=True)
    return scored
