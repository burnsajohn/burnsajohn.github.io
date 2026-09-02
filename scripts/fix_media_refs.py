#!/usr/bin/env python3
"""
Update .qmd references after scripts/shrink_media.sh converts media.

    python3 scripts/fix_media_refs.py --dry-run
    python3 scripts/fix_media_refs.py

Two jobs:

  1. Stills that changed extension (PNG -> JPG). A plain path rewrite,
     entirely safe, done silently.

  2. GIFs that became MP4s. An image reference cannot point at a video,
     so the markdown has to become a <video> tag. That is a structural
     change, so every one is reported and the original file is backed up
     first.

It works out what changed by comparing the .qmd files against what is
actually on disk: a reference to a file that no longer exists, where a
converted version does, is one to fix.

Standard library only.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "images"

# Two forms, matched in this order so the linked one is consumed whole.
# A single conditional regex looked tidier but left the trailing ](href)
# behind when the image became a block-level <video>.
LINKED = re.compile(
    r"\[!\[(?P<caption>[^\]]*)\]"
    r"\((?P<path>[^)\s]+?)\)"
    r"(?P<attrs>\{[^}]*\})?"
    r"\]\((?P<href>[^)\s]+?)\)"
)

PLAIN = re.compile(
    r"!\[(?P<caption>[^\]]*)\]"
    r"\((?P<path>[^)\s]+?)\)"
    r"(?P<attrs>\{[^}]*\})?"
)


def qmd_files():
    return sorted(list(ROOT.glob("*.qmd")) + list(ROOT.glob("projects/*.qmd")))


def resolve(qmd, path):
    """Where a path in a .qmd actually points on disk."""
    return (qmd.parent / path).resolve()


def alt_from(attrs, caption, fallback):
    if attrs:
        m = re.search(r'fig-alt="([^"]*)"', attrs)
        if m:
            return m.group(1)
    return caption or fallback


def video_block(src, alt, controls):
    """Raw HTML, since an image tag cannot carry a video."""
    if controls:
        opening = '<video controls preload="metadata">'
    else:
        opening = "<video autoplay loop muted playsinline>"
    return (f"{opening}\n"
            f'  <source src="{src}" type="video/mp4">\n'
            f"  {alt}\n"
            f"</video>")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change without writing")
    ap.add_argument("--controls", action="store_true",
                    help="give converted videos playback controls instead of "
                         "autoplay-loop. Autoplay-loop is the default because "
                         "it matches how the GIF behaved.")
    args = ap.parse_args()

    if not IMAGE_DIR.is_dir():
        sys.exit(f"{IMAGE_DIR} not found. Run this from the project root.")

    renames, videos, missing = [], [], []

    for qmd in qmd_files():
        original = qmd.read_text(encoding="utf-8")
        text = original

        for m in list(LINKED.finditer(original)) + list(PLAIN.finditer(original)):
            path = m.group("path")
            if not path.lower().endswith((".gif", ".png", ".jpg", ".jpeg")):
                continue

            if m.group(0) not in text:
                continue          # already handled by an earlier match

            on_disk = resolve(qmd, path)
            if on_disk.exists():
                continue          # nothing to fix

            stem = on_disk.with_suffix("")

            # PNG that became a JPEG.
            if on_disk.suffix.lower() == ".png" and stem.with_suffix(".jpg").exists():
                new_path = str(Path(path).with_suffix(".jpg"))
                text = text.replace(path, new_path)
                renames.append((qmd.name, path, new_path))
                continue

            # GIF that became an MP4. The whole construct is replaced,
            # including any surrounding link, because a block-level
            # <video> cannot sit inside markdown link brackets.
            if on_disk.suffix.lower() == ".gif" and stem.with_suffix(".mp4").exists():
                new_src = str(Path(path).with_suffix(".mp4"))
                alt = alt_from(m.group("attrs"), m.group("caption"),
                               stem.name.replace("-", " ").replace("_", " "))
                block = video_block(new_src, alt, args.controls)
                text = text.replace(m.group(0), block)
                videos.append((qmd.name, path, new_src))
                continue

            missing.append((qmd.name, path))

        if text != original and not args.dry_run:
            shutil.copy2(qmd, qmd.with_suffix(".qmd.bak"))
            qmd.write_text(text, encoding="utf-8")

    # ---------------------------------------------------------------- report
    if renames:
        print(f"Renamed {len(renames)} still image reference(s):")
        for f, old, new in renames:
            print(f"  {f}: {Path(old).name} -> {Path(new).name}")
        print()

    if videos:
        style = "controls" if args.controls else "autoplay, looping, muted"
        print(f"Converted {len(videos)} image reference(s) to <video> ({style}):")
        for f, old, new in videos:
            print(f"  {f}: {Path(old).name} -> {Path(new).name}")
        print()
        print("  Check these in preview. A video inside a .gallery or")
        print("  .figure-col will not inherit the image styling, so the")
        print("  layout around it may need adjusting by hand.")
        print()

    if missing:
        print("Referenced files that do not exist and have no converted")
        print("version. These are broken links, not conversion leftovers:")
        for f, path in missing:
            print(f"  {f}: {path}")
        print()

    if not (renames or videos or missing):
        print("Nothing to fix. Every referenced file is on disk.")
        return

    if args.dry_run:
        print("Dry run: no files were written.")
    elif renames or videos:
        print("Originals saved alongside each edited file as .qmd.bak")
        print("Remove them once you have checked the pages:")
        print("  rm *.qmd.bak projects/*.qmd.bak")


if __name__ == "__main__":
    main()
