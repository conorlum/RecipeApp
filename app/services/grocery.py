import re

from app.services.normalize import normalize_name

CONOR_FIX_THIS = "Conor fix this"

_INT_OR_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")
_SIMPLE_FRACTION = re.compile(r"^(\d+)\s*/\s*(\d+)$")
_MIXED_FRACTION = re.compile(r"^(\d+)\s+(\d+)\s*/\s*(\d+)$")


def parse_plain_number(text):
    """Return a float if `text` is a plain number or simple/mixed fraction,
    else None. Per spec: "No unit conversion in v1, except vague-quantity
    phrases via the equivalency table" — this is the line between "exact"
    and "vague"."""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None

    if _INT_OR_DECIMAL.match(text):
        return float(text)

    mixed = _MIXED_FRACTION.match(text)
    if mixed:
        whole, num, den = mixed.groups()
        return float(whole) + float(num) / float(den)

    simple = _SIMPLE_FRACTION.match(text)
    if simple:
        num, den = simple.groups()
        return float(num) / float(den)

    return None


def format_quantity(value):
    rounded = round(value, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def format_scale(scale):
    return f"{format_quantity(scale)}x"


def build_equivalency_lookup(equivalencies):
    """equivalencies: iterable of QuantityEquivalency rows."""
    return {normalize_name(e.phrase): (e.quantity, e.unit) for e in equivalencies}


def resolve_ingredient(name, quantity_raw, unit_raw, equivalency_lookup):
    """Resolve one raw recipe ingredient into either an exact (quantity, unit)
    pair, or an unresolved vague-quantity marker.

    Returns a dict:
      {"name": normalized name, "raw_name": original name,
       "resolved": bool,
       "quantity": float or None (only when resolved),
       "unit": str or None (normalized, only when resolved),
       "vague_text": original quantity text (only when not resolved)}
    """
    normalized_name = normalize_name(name)
    unit_norm = normalize_name(unit_raw) if unit_raw else None

    plain = parse_plain_number(quantity_raw)
    if plain is not None:
        return {
            "name": normalized_name,
            "raw_name": name,
            "resolved": True,
            "quantity": plain,
            "unit": unit_norm,
        }

    phrase = normalize_name(quantity_raw) if quantity_raw else (unit_norm or "")
    if phrase and phrase in equivalency_lookup:
        eq_quantity, eq_unit = equivalency_lookup[phrase]
        return {
            "name": normalized_name,
            "raw_name": name,
            "resolved": True,
            "quantity": eq_quantity,
            "unit": normalize_name(eq_unit),
        }

    vague_text = quantity_raw or unit_raw or ""
    return {
        "name": normalized_name,
        "raw_name": name,
        "resolved": False,
        "vague_text": vague_text,
    }


def expand_recipe_ingredients(recipe, scale, equivalency_lookup):
    """Resolve + scale every ingredient on a recipe. Returns a list of line
    dicts ready for combine_lines()."""
    lines = []
    for ing in recipe.ingredients or []:
        resolved = resolve_ingredient(
            ing.get("name", ""), ing.get("quantity"), ing.get("unit"), equivalency_lookup
        )
        if not resolved["name"]:
            continue

        if resolved["resolved"]:
            lines.append(
                {
                    "name": resolved["name"],
                    "raw_name": resolved["raw_name"],
                    "quantity": resolved["quantity"] * scale,
                    "unit": resolved["unit"],
                }
            )
        else:
            lines.append(
                {
                    "name": resolved["name"],
                    "raw_name": resolved["raw_name"],
                    "quantity": None,
                    "unit": CONOR_FIX_THIS,
                    "display_quantity": format_scale(scale),
                    "vague_text": resolved["vague_text"],
                }
            )
    return lines


def combine_lines(lines):
    """Combine a flat list of ingredient lines (possibly from multiple
    recipes) into grocery-list-item-shaped dicts: sum quantity when
    name+unit match exactly; leave unresolved ("Conor fix this") lines as
    separate entries, one per occurrence."""
    exact = {}
    combined = []

    for line in lines:
        if line["quantity"] is None:
            combined.append(
                {
                    "name": line["name"],
                    "quantity": line["display_quantity"],
                    "unit": CONOR_FIX_THIS,
                }
            )
            continue

        key = (line["name"], line["unit"])
        if key not in exact:
            exact[key] = 0.0
        exact[key] += line["quantity"]

    for (name, unit), total in exact.items():
        combined.append({"name": name, "quantity": format_quantity(total), "unit": unit})

    return combined


def drop_pantry_items(items, pantry_names_normalized):
    pantry_set = set(pantry_names_normalized)
    return [item for item in items if item["name"] not in pantry_set]


def merge_lines_into_list(grocery_list, lines, pantry_names_normalized):
    """Core flow #12: merge a single recipe's (already scaled/resolved)
    ingredient lines into an existing GroceryList's items, after pantry
    subtraction. Mutates grocery_list.items via SQLAlchemy (caller commits).
    """
    from app.models import GroceryListItem

    pantry_set = set(pantry_names_normalized)

    existing_by_key = {
        (item.name, item.unit): item
        for item in grocery_list.items
        if item.source == "recipe"
    }

    for line in lines:
        if line["name"] in pantry_set:
            continue

        if line["quantity"] is None:
            # Unresolved vague quantity: always a new row, never summed.
            grocery_list.items.append(
                GroceryListItem(
                    name=line["name"],
                    quantity=line["display_quantity"],
                    unit=CONOR_FIX_THIS,
                    source="recipe",
                    checked=False,
                )
            )
            continue

        key = (line["name"], line["unit"])
        existing = existing_by_key.get(key)
        if existing is None:
            new_item = GroceryListItem(
                name=line["name"],
                quantity=format_quantity(line["quantity"]),
                unit=line["unit"],
                source="recipe",
                checked=False,
            )
            grocery_list.items.append(new_item)
            existing_by_key[key] = new_item
        else:
            current = parse_plain_number(existing.quantity) or 0.0
            existing.quantity = format_quantity(current + line["quantity"])
            if existing.checked:
                existing.checked = False
