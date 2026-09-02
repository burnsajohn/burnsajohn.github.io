#!/usr/bin/env python3
"""
Regenerate gallery.qmd from whatever is in images/gallery/.

    python3 scripts/update_gallery.py

Organisation comes from the filesystem. Files directly in images/gallery/
appear first, ungrouped. Each subdirectory becomes its own section, with a
heading made from the directory name, so grouping images means moving files
rather than editing markdown.

    images/gallery/
        someshot.jpg              -> first, ungrouped
        radiolarians/
            acanth.png            -> under "Radiolarians"
        deep-sea/
            tomopteris.jpg        -> under "Deep sea"

Alt text and captions live in images/gallery/captions.txt, one line per file:

    acanth.png: An acantharian in polarised light
    tomopteris.jpg: A tomopterid polychaete | Tomopteris sp., in situ

Everything before the colon is the filename, which does not need its
directory. After it is the alt text. An optional caption follows a pipe.
Files with no entry get a placeholder alt and are listed when the script
runs, so nothing is silently inaccessible.

Video files are handled too, and take their alt and caption from the same
file. They are emitted differently from images:

  Images are written as plain markdown with no surrounding link. Quarto's
  lightbox (lightbox: auto in _quarto.yml) only sees images that are
  block-level, and an image wrapped in a markdown link is inline, so
  hand-wrapping one both defeats the lightbox and drops its caption into
  the alt slot.

  Videos get a hand-written anchor, because the lightbox filter does not
  handle video at all. They are wrapped in <figure> so they carry a
  caption the same way an image does.

Both need `images/gallery/**` under `resources:` in _quarto.yml, and the
theme needs `.gallery video` alongside `.gallery img` so videos are sized
and cropped to the grid.

Standard library only.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GALLERY_DIR = ROOT / "images" / "gallery"
CAPTIONS = GALLERY_DIR / "captions.txt"
OUTPUT = ROOT / "gallery.qmd"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# Sections appear in this order if present; anything else follows
# alphabetically. Names are directory names, lower case.
SECTION_ORDER = [
    "radiolarians",
    "salamanders",
    "deep-sea",
    "field",
]

LEAD = "Images from the lab, the field, and the microscope."


def read_captions():
    """filename -> (alt, caption or None). Missing file is fine."""
    out = {}
    if not CAPTIONS.exists():
        return out
    for i, raw in enumerate(CAPTIONS.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            print(f"  captions.txt line {i}: no colon, skipped", file=sys.stderr)
            continue
        name, rest = line.split(":", 1)
        alt, caption = rest, None
        if "|" in rest:
            alt, caption = rest.split("|", 1)
        out[name.strip()] = (alt.strip(), (caption or "").strip() or None)
    return out


def heading_for(dirname):
    """radiolarians -> Radiolarians;  deep-sea -> Deep sea."""
    words = dirname.replace("_", " ").replace("-", " ").split()
    if not words:
        return dirname
    return " ".join([words[0].capitalize()] + [w.lower() for w in words[1:]])


def media_in(directory):
    return sorted(
        (p for p in directory.iterdir()
         if p.is_file() and p.suffix.lower() in MEDIA_EXTS),
        key=lambda p: p.name.lower(),
    )


def esc(text):
    """Markdown link and attribute text needs its brackets and quotes tame."""
    return text.replace('"', "'").replace("[", "(").replace("]", ")")


def esc_html(text):
    """Text going into an HTML attribute or element body."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def image_entry(rel, alt, caption):
    """Plain markdown. No surrounding link: lightbox adds its own anchor,
    and a hand-written one would make the image inline and skip it."""
    cap = esc(caption) if caption else ""
    return [f'![{cap}]({rel}){{fig-alt="{esc(alt)}"}}']


def video_entry(rel, alt, caption):
    """Hand-written anchor, because the lightbox filter is images only.
    <figure> so the caption sits where an image's caption would."""
    lines = [
        "<figure>",
        f'<a href="{rel}">',
        f'<video src="{rel}" autoplay loop muted playsinline '
        f'aria-label="{esc_html(alt)}"></video>',
        "</a>",
    ]
    if caption:
        lines.append(f"<figcaption>{esc_html(caption)}</figcaption>")
    lines.append("</figure>")
    return lines


def block(paths, captions, missing):
    lines = ["::: {.gallery}"]
    for p in paths:
        rel = p.relative_to(ROOT).as_posix()
        alt, caption = captions.get(p.name, (None, None))
        if alt is None:
            missing.append(p.name)
            alt = "TODO: describe this image"
        lines.append("")
        if p.suffix.lower() in VIDEO_EXTS:
            lines += video_entry(rel, alt, caption)
        else:
            lines += image_entry(rel, alt, caption)
    lines.append("")
    lines.append(":::")
    return lines


def main():
    if not GALLERY_DIR.is_dir():
        sys.exit(f"{GALLERY_DIR} does not exist.")

    captions = read_captions()
    missing = []

    out = [
        "---",
        'title: "Gallery"',
        "---",
        "",
        "<!-- Generated by scripts/update_gallery.py. Do not edit by hand.",
        "     Add images to images/gallery/ or a subdirectory of it, write",
        "     alt text in images/gallery/captions.txt, and re-run. -->",
        "",
        "::: {.lead}",
        LEAD,
        ":::",
        "",
    ]

    loose = media_in(GALLERY_DIR)
    if loose:
        out += block(loose, captions, missing)
        out.append("")

    subdirs = sorted(
        (d for d in GALLERY_DIR.iterdir() if d.is_dir()),
        key=lambda d: (SECTION_ORDER.index(d.name.lower())
                       if d.name.lower() in SECTION_ORDER
                       else len(SECTION_ORDER), d.name.lower()),
    )

    total = len(loose)
    videos = sum(1 for p in loose if p.suffix.lower() in VIDEO_EXTS)
    for d in subdirs:
        paths = media_in(d)
        if not paths:
            continue
        total += len(paths)
        videos += sum(1 for p in paths if p.suffix.lower() in VIDEO_EXTS)
        out.append(f"## {heading_for(d.name)}")
        out.append("")
        out += block(paths, captions, missing)
        out.append("")

    OUTPUT.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote {OUTPUT.name}: {total - videos} images, {videos} videos"
          f"{f' in {len(subdirs)} sections' if subdirs else ''}.")

    if missing:
        print(f"\n{len(missing)} without alt text. Add lines to "
              f"{CAPTIONS.relative_to(ROOT)}:", file=sys.stderr)
        for name in missing:
            print(f"  {name}: ", file=sys.stderr)

    unused = [k for k in captions if k not in
              {p.name for p in loose} | {p.name for d in subdirs
                                         for p in media_in(d)}]
    if unused:
        print(f"\ncaptions.txt entries matching no file:", file=sys.stderr)
        for name in unused:
            print(f"  - {name}", file=sys.stderr)


if __name__ == "__main__":
    main()