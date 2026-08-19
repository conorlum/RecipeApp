from datetime import date

from app.services.normalize import normalize_name

# Northern Hemisphere (US) harvest seasonality by month. Approximate — meant
# to power "what's in season" suggestions, not to be an authoritative source.
SEASONAL_PRODUCE_BY_MONTH = {
    1: [  # vegetables
        "cabbage", "kale", "collard greens", "brussels sprouts", "leek",
        "parsnip", "turnip", "rutabaga", "winter squash", "sweet potato",
        "celery root", "fennel", "radicchio", "endive", "watercress",
        "mushroom",
        # fruits
        "orange", "blood orange", "grapefruit", "tangerine", "clementine",
        "mandarin", "kumquat", "pear", "pomegranate", "kiwi", "date",
    ],
    2: [  # vegetables
        "cabbage", "kale", "collard greens", "brussels sprouts", "leek",
        "parsnip", "turnip", "rutabaga", "winter squash", "sweet potato",
        "celery root", "fennel", "radicchio", "endive", "watercress",
        "mushroom",
        # fruits
        "orange", "blood orange", "grapefruit", "tangerine", "clementine",
        "mandarin", "kumquat", "pear", "pomegranate", "kiwi",
    ],
    3: [  # vegetables
        "asparagus", "artichoke", "spinach", "arugula", "radish",
        "spring onion", "pea", "fava bean", "rhubarb", "kale", "cabbage",
        "leek", "watercress", "fennel", "mushroom", "fiddlehead fern",
        # fruits
        "orange", "grapefruit", "strawberry", "kiwi",
    ],
    4: [  # vegetables
        "asparagus", "artichoke", "spinach", "arugula", "radish",
        "spring onion", "pea", "fava bean", "rhubarb", "new potato",
        "spring garlic", "morel mushroom", "fiddlehead fern", "watercress",
        "lettuce", "chive",
        # fruits
        "strawberry", "apricot",
    ],
    5: [  # vegetables
        "asparagus", "pea", "fava bean", "rhubarb", "spring onion", "radish",
        "arugula", "spinach", "new potato", "garlic scape", "lettuce",
        "chive", "mint",
        # fruits
        "strawberry", "cherry", "apricot",
    ],
    6: [  # vegetables
        "zucchini", "summer squash", "green bean", "pea", "garlic",
        "new potato", "cucumber", "tomato", "carrot", "beet", "fennel",
        "chard", "basil", "dill", "mint",
        # fruits
        "strawberry", "cherry", "blueberry", "apricot", "peach", "currant",
        "gooseberry", "mulberry", "elderberry",
    ],
    7: [  # vegetables
        "tomato", "corn", "zucchini", "summer squash", "cucumber",
        "green bean", "bell pepper", "eggplant", "okra", "carrot", "beet",
        "chard", "basil", "dill", "cilantro", "tomatillo",
        # fruits
        "peach", "plum", "blueberry", "blackberry", "raspberry",
        "watermelon", "cantaloupe", "cherry", "boysenberry", "fig",
        "nectarine",
    ],
    8: [  # vegetables
        "tomato", "corn", "zucchini", "summer squash", "cucumber",
        "green bean", "bell pepper", "hot pepper", "eggplant", "okra",
        "tomatillo", "basil", "chard",
        # fruits
        "peach", "plum", "pluot", "nectarine", "blueberry", "blackberry",
        "raspberry", "watermelon", "cantaloupe", "honeydew", "fig", "grape",
    ],
    9: [  # vegetables
        "tomato", "corn", "bell pepper", "hot pepper", "eggplant",
        "winter squash", "pumpkin", "sweet potato", "broccoli",
        "cauliflower", "brussels sprouts", "celery", "mushroom", "leek",
        "kale",
        # fruits
        "apple", "pear", "grape", "fig", "plum", "quince", "pomegranate",
    ],
    10: [  # vegetables
        "pumpkin", "winter squash", "sweet potato", "broccoli",
        "cauliflower", "brussels sprouts", "cabbage", "kale", "parsnip",
        "turnip", "celery root", "mushroom", "radicchio", "endive", "leek",
        "beet",
        # fruits
        "apple", "pear", "grape", "fig", "cranberry", "persimmon", "quince",
        "pomegranate",
    ],
    11: [  # vegetables
        "pumpkin", "winter squash", "sweet potato", "brussels sprouts",
        "cauliflower", "broccoli", "kale", "cabbage", "parsnip", "turnip",
        "leek", "celery root", "rutabaga", "watercress",
        # fruits
        "apple", "pear", "cranberry", "persimmon", "pomegranate", "quince",
        "kiwi", "date",
    ],
    12: [  # vegetables
        "cabbage", "kale", "collard greens", "brussels sprouts",
        "winter squash", "sweet potato", "leek", "parsnip", "celery root",
        "rutabaga", "fennel", "watercress", "endive",
        # fruits
        "orange", "tangerine", "clementine", "grapefruit", "pomegranate",
        "persimmon", "pear", "cranberry", "kiwi", "date",
    ],
}


def in_season_now(today=None):
    """Normalized produce names in season for the current month."""
    today = today or date.today()
    return [normalize_name(name) for name in SEASONAL_PRODUCE_BY_MONTH.get(today.month, [])]


def _ingredient_is_in_season(ingredient_name, in_season_set):
    name = normalize_name(ingredient_name)
    if not name:
        return False
    return any(produce in name or name in produce for produce in in_season_set)


def seasonal_matches(recipe, in_season_set):
    """Names of a recipe's ingredients that are currently in season."""
    return [
        ing.get("name", "")
        for ing in recipe.ingredients or []
        if ing.get("name") and _ingredient_is_in_season(ing["name"], in_season_set)
    ]


def rank_by_seasonality(recipes, in_season_set):
    """Score + sort recipes by how many current in-season ingredients they use.
    Returns (recipe, matches) pairs sorted by match count descending; recipes
    with no in-season ingredients are excluded."""
    scored = [(recipe, seasonal_matches(recipe, in_season_set)) for recipe in recipes]
    scored = [pair for pair in scored if pair[1]]
    scored.sort(key=lambda pair: len(pair[1]), reverse=True)
    return scored
