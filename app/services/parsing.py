import base64
import json
import re

import requests
from bs4 import BeautifulSoup
from flask import current_app

SYSTEM_PROMPT = """You extract recipes from raw text (a web page's text content, or a \
pasted Instagram caption). Return ONLY valid JSON, no commentary, no markdown fences.

If you can find a usable recipe (ingredients and/or steps) in the text, return exactly \
this shape:
{"title": "...", "servings": null, "ingredients": [{"name": "...", "quantity": "...", "unit": "..."}], "steps": ["...", "..."]}

"servings" should be a number if the source explicitly states one (e.g. "serves 4"), \
otherwise null - do not guess.

If no usable recipe (no real ingredients or steps) can be found in the text, return \
exactly this shape instead:
{"error": "Couldn't find any ingredients or steps in this text."}

The error message should briefly explain, in your own words, why nothing usable was found."""

_UNITS = [
    "tablespoons", "tablespoon", "tbsp", "teaspoons", "teaspoon", "tsp",
    "cups", "cup", "ounces", "ounce", "oz", "pounds", "pound", "lbs", "lb",
    "grams", "gram", "g", "kilograms", "kilogram", "kg", "milliliters",
    "milliliter", "ml", "liters", "liter", "l", "pinch", "pinches", "dash",
    "dashes", "cloves", "clove", "slices", "slice", "cans", "can",
    "packages", "package", "pkg", "sticks", "stick", "bunches", "bunch",
    "heads", "head", "large", "medium", "small",
]
_UNIT_PATTERN = "|".join(sorted(_UNITS, key=len, reverse=True))
_QTY_RE = re.compile(
    r"""^\s*
    (?P<qty>\d+\s*\d*/\d+ | \d+(\.\d+)?\s*-\s*\d+(\.\d+)? | \d+(\.\d+)?)
    \s*
    (?P<unit>""" + _UNIT_PATTERN + r""")?
    \b\.?\s*
    (?P<rest>.*)$""",
    re.VERBOSE | re.IGNORECASE,
)


def parse_ingredient_line(line):
    """Best-effort split of a freeform ingredient line into name/quantity/unit.

    Used only for the JSON-LD website path, which skips the Claude call
    entirely per the handoff spec ("try JSON-LD first"). No unit conversion,
    just a leading-quantity/unit split; falls back to the whole line as the
    name when nothing parses.
    """
    line = line.strip()
    if not line:
        return {"name": "", "quantity": None, "unit": None}

    match = _QTY_RE.match(line)
    if not match:
        return {"name": line, "quantity": None, "unit": None}

    qty = match.group("qty")
    unit = match.group("unit")
    rest = match.group("rest").strip(" ,")
    if not rest:
        rest = line
        qty = None
        unit = None

    return {
        "name": rest,
        "quantity": qty.strip() if qty else None,
        "unit": unit.lower() if unit else None,
    }


def extract_jsonld_recipe(soup):
    """Look for a schema.org Recipe in the page's JSON-LD blocks. Returns the
    parsed {title, servings, ingredients, steps} dict, or None if no Recipe
    block is present."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        # Some sites wrap the graph in {"@graph": [...]}.
        expanded = []
        for c in candidates:
            if isinstance(c, dict) and "@graph" in c:
                expanded.extend(c["@graph"])
            else:
                expanded.append(c)

        for item in expanded:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if "Recipe" not in types:
                continue
            return _recipe_from_jsonld(item)

    return None


def _recipe_from_jsonld(item):
    title = item.get("name") or ""

    servings = None
    raw_yield = item.get("recipeYield")
    if isinstance(raw_yield, list):
        raw_yield = raw_yield[0] if raw_yield else None
    if raw_yield:
        digits = re.search(r"\d+", str(raw_yield))
        if digits:
            servings = int(digits.group())

    ingredients = []
    for raw_line in item.get("recipeIngredient") or item.get("ingredients") or []:
        if isinstance(raw_line, str):
            ingredients.append(parse_ingredient_line(raw_line))

    steps = []
    instructions = item.get("recipeInstructions") or []
    if isinstance(instructions, str):
        steps = [s.strip() for s in instructions.split("\n") if s.strip()]
    elif isinstance(instructions, list):
        for step in instructions:
            if isinstance(step, str):
                steps.append(step.strip())
            elif isinstance(step, dict):
                text = step.get("text") or step.get("name")
                if text:
                    steps.append(text.strip())

    if not ingredients and not steps:
        return None

    return {"title": title, "servings": servings, "ingredients": ingredients, "steps": steps}


def fetch_website(url):
    """Fetch a URL and return (page_html, visible_text)."""
    response = requests.get(
        url,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (recipe-app import bot)"},
    )
    response.raise_for_status()
    html = response.text

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    visible_text = re.sub(r"\n{2,}", "\n", soup.get_text("\n")).strip()

    return html, visible_text


def _call_claude(content):
    """Shared Claude call + JSON parse for both the text and image paths.
    `content` is whatever the Messages API accepts as a single user turn's
    content: a raw string, or a list of content blocks (e.g. image + text)."""
    import anthropic

    client = anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(block.text for block in message.content if block.type == "text").strip()

    try:
        return json.loads(text)
    except ValueError:
        return {"error": "Claude returned something that wasn't valid JSON. Try re-parsing."}


def parse_recipe_with_claude(raw_text):
    """Send raw_text to Claude for structured recipe extraction. Returns the
    parsed recipe dict, or {"error": "..."} if Claude couldn't find one."""
    return _call_claude(raw_text)


def parse_recipe_image_with_claude(image_bytes, media_type="image/jpeg"):
    """Same extraction as parse_recipe_with_claude, but from a screenshot:
    Claude reads on-screen text directly from the image (vision), no
    separate OCR step. Same JSON output shape, same error handling."""
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
        {"type": "text", "text": "Extract the recipe from this screenshot."},
    ]
    return _call_claude(content)


def import_from_website(url):
    """Core flow #2: fetch a URL, try JSON-LD first, fall back to Claude on
    the page's visible text. Returns (parsed_dict, raw_text_for_storage)."""
    html, visible_text = fetch_website(url)
    soup = BeautifulSoup(html, "html.parser")

    jsonld_recipe = extract_jsonld_recipe(soup)
    if jsonld_recipe is not None:
        return jsonld_recipe, visible_text

    return parse_recipe_with_claude(visible_text), visible_text


def import_from_instagram(raw_text):
    """Core flow #3: parse a pasted Instagram caption via Claude."""
    return parse_recipe_with_claude(raw_text), raw_text


def fetch_instagram_caption(url):
    """Instagram ingestion path 1 (Shortcut share-sheet): try fetching the
    post's public page and pulling the caption out of its page metadata
    (same fetch logic as website import). Returns the caption text, or None
    if the page couldn't be fetched or has no caption metadata (private
    account, blocked fetch, etc.) — the caller treats None as "save a stub"
    per the handoff spec, rather than failing the request."""
    try:
        html, _ = fetch_website(url)
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", property="og:description")
    if meta and meta.get("content"):
        return meta["content"].strip()
    return None
