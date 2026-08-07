"""Terminal workaround for the needs_review queue that doesn't call Claude
via the API (and so doesn't need ANTHROPIC_API_KEY / bill per recipe).

Usage:
    python scripts/review_queue.py list
        Dumps every needs_review recipe's raw_text/raw_image to
        instance/review_queue.json (and instance/review_images/<id>.<ext>
        for screenshots) with a blank "parsed" field per entry.

    <fill in the "parsed" field for each entry by hand, or by having
    someone/something read the raw_text / screenshot and write out
    {"title": ..., "servings": ..., "ingredients": [...], "steps": [...],
    "tags": [...]}>

    python scripts/review_queue.py apply
        Reads instance/review_queue.json back, applies every entry whose
        "parsed" field is filled in to the matching Recipe row, and clears
        needs_review. Entries left with "parsed": null are skipped and stay
        in the queue.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models import Recipe

INSTANCE_DIR = Path(__file__).resolve().parent.parent / "instance"
QUEUE_PATH = INSTANCE_DIR / "review_queue.json"
IMAGES_DIR = INSTANCE_DIR / "review_images"


def _image_extension(image_bytes):
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "jpg"
    return "bin"


def cmd_list(_args):
    app = create_app()
    with app.app_context():
        recipes = Recipe.query.filter_by(needs_review=True).order_by(Recipe.created_at).all()

        if not recipes:
            print("Nothing in the needs_review queue.")
            QUEUE_PATH.write_text("[]\n")
            return

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        entries = []
        for recipe in recipes:
            image_path = None
            if recipe.raw_image:
                ext = _image_extension(recipe.raw_image)
                image_path = IMAGES_DIR / f"{recipe.id}.{ext}"
                image_path.write_bytes(recipe.raw_image)

            entries.append(
                {
                    "id": recipe.id,
                    "source_type": recipe.source_type,
                    "source_url": recipe.source_url,
                    "raw_text": recipe.raw_text,
                    "image_path": str(image_path) if image_path else None,
                    "current_title": recipe.title,
                    "parsed": None,
                }
            )

        QUEUE_PATH.write_text(json.dumps(entries, indent=2))
        print(f"Wrote {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} to {QUEUE_PATH}")
        for entry in entries:
            print(f"  #{entry['id']}: {entry['current_title']} ({entry['source_url'] or 'no url'})")
        print(f'\nFill in "parsed" for each entry, then run: python scripts/review_queue.py apply')


def cmd_apply(_args):
    if not QUEUE_PATH.exists():
        print(f"No queue file at {QUEUE_PATH}. Run `list` first.")
        return

    entries = json.loads(QUEUE_PATH.read_text())

    app = create_app()
    with app.app_context():
        applied, skipped = [], []
        for entry in entries:
            parsed = entry.get("parsed")
            if not parsed:
                skipped.append(entry["id"])
                continue

            recipe = Recipe.query.get(entry["id"])
            if recipe is None:
                print(f"  #{entry['id']}: no such recipe, skipping")
                skipped.append(entry["id"])
                continue

            recipe.title = parsed.get("title") or recipe.title
            recipe.servings = parsed.get("servings")
            recipe.ingredients = parsed.get("ingredients") or []
            recipe.steps = parsed.get("steps") or []
            recipe.tags = parsed.get("tags") or []
            recipe.needs_review = False
            applied.append(recipe.id)

        db.session.commit()

    print(f"Applied: {applied or 'none'}")
    print(f"Skipped (still needs_review, no parsed data yet): {skipped or 'none'}")

    remaining = [e for e in entries if e["id"] in skipped]
    QUEUE_PATH.write_text(json.dumps(remaining, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Dump the needs_review queue to instance/review_queue.json").set_defaults(func=cmd_list)
    sub.add_parser("apply", help="Apply filled-in parsed data back to the recipes").set_defaults(func=cmd_apply)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
