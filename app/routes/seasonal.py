from datetime import date

from flask import Blueprint, g, render_template

from app.auth_utils import login_required
from app.models import Recipe
from app.services.seasonal import SEASONAL_PRODUCE_BY_MONTH, in_season_now, rank_by_seasonality

bp = Blueprint("seasonal", __name__, url_prefix="/seasonal")

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@bp.route("")
@login_required
def suggestions():
    today = date.today()
    in_season_set = set(in_season_now(today))
    produce = SEASONAL_PRODUCE_BY_MONTH.get(today.month, [])

    recipes = Recipe.query.filter_by(owner_id=g.user.id).all()
    ranked = rank_by_seasonality(recipes, in_season_set)

    return render_template(
        "seasonal/index.html",
        month_name=_MONTH_NAMES[today.month - 1],
        produce=produce,
        ranked=ranked,
    )
