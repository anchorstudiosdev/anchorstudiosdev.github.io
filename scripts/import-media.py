"""Copy a tool's store screenshots and social image into the site, sized for the web.

Usage: python scripts/import-media.py <tool id> <path to the tool's Publishing folder>

Reads <folder>/screenshots/<id>-NN-name.png, their titles from <folder>/screens.js, and from
<folder>/key-art/ the social image and the card, preferring the card rendered at 2x
(node render.mjs <outRoot> 2 in Publishing/artboards). Writes src/img/tools/<id>/: each screenshot as a
1600 px WebP with a 480 px thumbnail, the social image as a WebP for the page and a JPEG for link
previews, the card as a WebP, and media.json, which build-docs.py reads. Run it again whenever the
store media change, then rebuild the docs page.
"""
import argparse
import json
import pathlib
import re

from PIL import Image

SITE = pathlib.Path(__file__).resolve().parent.parent
FULL_WIDTH = 1600
THUMB_WIDTH = 480


def card_titles(screens_js):
    """Each card's number mapped to its label and headline, as the card draws them."""
    text = screens_js.read_text(encoding="utf-8")
    titles = {}
    for match in re.finditer(r"eyebrow:\s*\['(\d+)',\s*'([^']+)'\],\s*title:\s*\[([^\]]*)\]", text):
        headline = " ".join(re.findall(r"'([^']*)'", match.group(3)))
        titles[match.group(1)] = (match.group(2).capitalize(), headline)
    return titles


def save(source, dest, width, quality):
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width > width:
            image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
        if dest.suffix == ".webp":
            image.save(dest, "WEBP", quality=quality, method=6)
        else:
            image.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
        return image.size


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tool_id")
    parser.add_argument("publishing")
    args = parser.parse_args()

    source = pathlib.Path(args.publishing)
    out = SITE / "src/img/tools" / args.tool_id
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():
        old.unlink()

    titles = card_titles(source / "screens.js")
    shots = []
    for png in sorted((source / "screenshots").glob(f"{args.tool_id}-*.png")):
        match = re.fullmatch(rf"{re.escape(args.tool_id)}-(\d+)-(.+)\.png", png.name)
        if not match:
            continue
        number, name = match.groups()
        stem = f"{number}-{name}"
        width, height = save(png, out / f"{stem}.webp", FULL_WIDTH, 82)
        save(png, out / f"{stem}-thumb.webp", THUMB_WIDTH, 78)
        label, headline = titles.get(number, (name.replace("-", " ").capitalize(), ""))
        shots.append({"src": f"{stem}.webp", "thumb": f"{stem}-thumb.webp", "label": label,
                      "title": headline, "width": width, "height": height})

    media = {"screenshots": shots}
    social = source / "key-art" / f"{args.tool_id}-social.png"
    if social.exists():
        save(social, out / "social.webp", 1200, 85)
        save(social, out / "social.jpg", 1200, 88)
        media["banner"] = "social.webp"
        media["preview"] = "social.jpg"

    art = source / "key-art"
    card = next((f for f in (art / f"{args.tool_id}-card@2x.png", art / f"{args.tool_id}-card.png")
                 if f.exists()), None)
    if card:
        save(card, out / "card.webp", 840, 88)
        media["card"] = "card.webp"

    (out / "media.json").write_text(json.dumps(media, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8", newline="\n")
    total = sum(f.stat().st_size for f in out.iterdir())
    print(f"{out.relative_to(SITE)}: {len(shots)} screenshots, {total // 1024} KB")


if __name__ == "__main__":
    main()
