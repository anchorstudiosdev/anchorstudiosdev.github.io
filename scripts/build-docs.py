"""Build a tool's documentation page from its README.

Usage: python scripts/build-docs.py <tool id> <path to README.md> [--version X.Y.Z]

Writes <tool id>/index.html. The tool's name, summary, accent and icon come from src/data/tools.json,
so the page matches its card. Edit the README, then run this again; never edit the output by hand.
"""
import argparse
import html
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent

# Line icons for section headings, drawn on a 24-unit grid in the same stroke style as the tool cards.
ICONS = {
    "sparkle": '<path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5z"/><path d="M19 17v4"/><path d="M17 19h4"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18c1.2 0 1.8-.8 1.8-1.7 0-1.1-.9-1.6-.9-2.5 0-.9.7-1.6 1.6-1.6H17a4 4 0 0 0 4-4c0-4.6-4-8.2-9-8.2z"/><circle cx="7.5" cy="12" r="1"/><circle cx="9.5" cy="7.5" r="1"/><circle cx="14.5" cy="7.5" r="1"/>',
    "chart": '<path d="M3 20h18"/><rect x="5" y="11" width="3" height="6" rx="0.5"/><rect x="10.5" y="5" width="3" height="12" rx="0.5"/><rect x="16" y="13" width="3" height="4" rx="0.5"/>',
    "branch": '<circle cx="6" cy="5" r="2"/><path d="M6 7v9a3 3 0 0 0 3 3h4"/><path d="M6 11h7"/><circle cx="15" cy="11" r="2"/><circle cx="15" cy="19" r="2"/>',
    "image": '<rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9.5" r="1.5"/><path d="M20 15l-4.5-4.5L7 19"/>',
    "check": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/>',
    "panel": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18"/><path d="M6 12.5h6"/><path d="M6 15.5h4"/><path d="M15 12.5h3"/><path d="M15 15.5h3"/>',
    "heading": '<rect x="3" y="9" width="18" height="6" rx="1.5"/><path d="M7 5h10"/><path d="M7 19h10"/>',
    "drop": '<path d="M12 4v10"/><path d="M8 10l4 4 4-4"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "keyboard": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h.01M11 10h.01M15 10h.01M17 10h.01"/><path d="M8 14h8"/>',
    "layers": '<path d="M12 4l9 5-9 5-9-5 9-5z"/><path d="M3 14l9 5 9-5"/>',
    "tag": '<path d="M4 4h7l9 9-7 7-9-9V4z"/><circle cx="8.5" cy="8.5" r="1.5"/>',
    "sliders": '<path d="M4 7h10M18 7h2"/><circle cx="16" cy="7" r="2"/><path d="M4 17h2M10 17h10"/><circle cx="8" cy="17" r="2"/>',
    "toolbar": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M6.5 6.5h.01M9.5 6.5h.01M12.5 6.5h.01"/>',
}

# First match wins, so the more specific words come first.
ICON_RULES = [
    (r"feature", "sparkle"),
    (r"setting", "gear"),
    (r"color|gradient|appearance", "palette"),
    (r"statistic|tooltip", "chart"),
    (r"tree|connector", "branch"),
    (r"icon", "image"),
    (r"checkbox|activation|toggle", "check"),
    (r"minimap|inspector", "panel"),
    (r"scene", "layers"),
    (r"header", "heading"),
    (r"drop", "drop"),
    (r"shortcut|hotkey|key", "keyboard"),
    (r"column|tag|layer", "tag"),
    (r"control", "sliders"),
    (r"toolbar|panel|window", "toolbar"),
]


def heading_icon(text):
    plain = html.unescape(re.sub(r"<[^>]+>", "", text)).lower()
    key = next((icon for pattern, icon in ICON_RULES if re.search(pattern, plain)), "sparkle")
    return ('<span class="doc-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + ICONS[key] + "</svg></span>")


def slugify(text, taken):
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[^\w\s-]", "", text.lower())
    slug = base = re.sub(r"[\s_]+", "-", text).strip("-")
    n = 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    taken.add(slug)
    return slug


def inline(text):
    """Escape a line of Markdown and apply code spans, links, bold and italics."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append("<code>" + html.escape(part[1:-1]) + "</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
        out.append(s)
    return "".join(out)


def render(markdown):
    """Convert the README's Markdown subset to HTML, returning (html, headings)."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    body, headings = [], []
    paragraph, list_stack = [], []
    anchors = set()

    def flush_paragraph():
        if paragraph:
            body.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_lists(depth=0):
        while len(list_stack) > depth:
            body.append("</li></ul>")
            list_stack.pop()

    in_code = False
    for raw in lines:
        if raw.strip().startswith("```"):
            flush_paragraph()
            close_lists()
            body.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            body.append(html.escape(raw))
            continue

        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            continue

        heading = re.match(r"(#{1,4})\s+(.*)", line)
        if heading:
            flush_paragraph()
            close_lists()
            level = len(heading.group(1))
            text = inline(heading.group(2).strip())
            anchor = slugify(text, anchors)
            if level > 1:
                headings.append((level, anchor, text))
            icon = heading_icon(text) if level in (2, 3) else ""
            body.append(f'<h{level} id="{anchor}">{icon}<span>{text}</span></h{level}>')
            continue

        if re.match(r"\s*-{3,}\s*$", line):
            flush_paragraph()
            close_lists()
            body.append("<hr>")
            continue

        item = re.match(r"(\s*)[-*]\s+(.*)", line)
        if item:
            flush_paragraph()
            depth = len(item.group(1).replace("\t", "  ")) // 2 + 1
            if depth > len(list_stack):
                while depth > len(list_stack):
                    body.append("<ul><li>")
                    list_stack.append(depth)
            else:
                close_lists(depth)
                body.append("</li><li>")
            body.append(inline(item.group(2)))
            continue

        if list_stack and raw.startswith("  "):
            body.append(" " + inline(line.strip()))
            continue

        close_lists()
        paragraph.append(line.strip())

    flush_paragraph()
    close_lists()
    return "\n".join(body), headings


def toc(headings):
    items = []
    for level, anchor, text in headings:
        if level in (2, 3):
            items.append(f'<li class="toc-{level}"><a href="#{anchor}">{text}</a></li>')
    return "<ul>" + "".join(items) + "</ul>"


def page(tool, content, headings, version):
    icon = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round" width="24" height="24">' + tool["icon"] + "</svg>")
    name = html.escape(tool["name"])
    summary = html.escape(tool["summary"])
    version_note = f'<span class="doc-version">Version {html.escape(version)}</span>' if version else ""
    store = tool.get("store")
    store_button = (f'<a class="btn btn-primary" href="{html.escape(store)}">View on Asset Store</a>'
                    if store else "")
    return f"""<!doctype html>
<!-- Generated from the {name} README by scripts/build-docs.py. Edit the README, then rebuild. -->
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} Documentation — Anchor Studios</title>
  <meta name="description" content="{summary}">
  <link rel="icon" type="image/png" sizes="32x32" href="../src/img/brand/favicon-32.png">
  <link rel="icon" type="image/png" sizes="48x48" href="../src/img/brand/favicon-48.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../src/css/styles.css">
  <link rel="stylesheet" href="../src/css/docs.css">
</head>
<body style="--tool-accent: {tool['accent']};">

  <header class="site-header">
    <div class="wrap header-inner">
      <a href="../" class="brand">
        <img src="../src/img/brand/mark-crisp-256.png" alt="">
        Anchor Studios
      </a>
      <nav>
        <a href="../#tools">Tools</a>
        <a href="mailto:contact.anchorstudios@gmail.com">Support</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="doc-hero">
      <div class="wrap doc-hero-inner">
        <div class="modal-icon">{icon}</div>
        <div>
          <div class="doc-eyebrow">Documentation {version_note}</div>
          <h1>{name}</h1>
          <p class="lede">{summary}</p>
          <div class="hero-actions">
            {store_button}
            <a class="btn btn-ghost" href="mailto:contact.anchorstudios@gmail.com">Contact support</a>
          </div>
        </div>
      </div>
    </section>

    <div class="wrap doc-layout">
      <nav class="doc-toc" aria-label="On this page">
        <div class="doc-toc-title">On this page</div>
        {toc(headings)}
      </nav>
      <article class="doc-content">
{content}
      </article>
    </div>
  </main>

  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div class="footer-brand">
        <img src="../src/img/brand/mark-crisp-256.png" alt="">
        Anchor Studios
      </div>
      <a class="footer-contact" href="mailto:contact.anchorstudios@gmail.com">contact.anchorstudios@gmail.com</a>
      <span class="copyright">&copy; 2026 Anchor Studios</span>
    </div>
  </footer>

</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tool_id")
    parser.add_argument("readme")
    parser.add_argument("--version")
    args = parser.parse_args()

    tools = json.loads((SITE / "src/data/tools.json").read_text(encoding="utf-8"))
    tool = next(t for t in tools if t["id"] == args.tool_id)

    markdown = pathlib.Path(args.readme).read_text(encoding="utf-8-sig")
    markdown = re.sub(r"\A\s*#\s+[^\n]*\n", "", markdown)
    content, headings = render(markdown)

    out = SITE / args.tool_id / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page(tool, content, headings, args.version), encoding="utf-8", newline="\n")
    print(out.relative_to(SITE))


if __name__ == "__main__":
    main()
