#!/usr/bin/env bash
#
# Shrink every oversized image and animation under images/ to web sizes.
#
#   bash scripts/shrink_media.sh --dry-run              # show what would change
#   bash scripts/shrink_media.sh                        # do it, all of images/
#   bash scripts/shrink_media.sh images/gallery         # only that directory
#   bash scripts/shrink_media.sh --keep-gif images/x    # shrink GIFs, don't convert
#
# The optional path limits the run to one directory. Scoping matters
# because re-encoding an already-compressed file loses a little quality
# every pass, so running over everything repeatedly degrades images that
# were fine to begin with.
#
# Originals are copied to ../originals/ before anything is touched, so
# nothing is destroyed. That folder sits outside the repo.
#
#   animated GIF -> MP4, 960px wide, FULL LENGTH, faststart for seeking
#   large MP4    -> re-encoded, 960px wide, full length
#   TIFF         -> JPEG, always, at any size (browsers cannot show TIFF)
#   large PNG    -> JPEG if photographic, resized if line art
#   large JPEG   -> resized to 2000px on the long edge
#
# Nothing is truncated. Clips keep their full duration.
#
# WHAT GETS DELETED. A conversion that changes the extension removes the
# original from images/ after the new file is written: GIF to MP4, PNG to
# JPEG, TIFF to JPEG. A resize or re-encode that keeps the extension
# overwrites in place. Either way the untouched original is in
# ../originals/ first, and that folder sits outside the repo so it is
# never committed. Deletions are staged by the next `git add -A`, which
# is what you want, since the old file is no longer referenced.
#
# --keep-gif shrinks animated GIFs in place instead of converting them.
# Expect far less compression: a GIF has no interframe compression and a
# 256-colour ceiling per frame, so the same clip can be ten times the size
# of its MP4. Use it where the file has to stay an image.
#
# The case that needs it is a page's `image:` front matter field. That
# renders as an <img> on listing cards, so an MP4 there is a broken
# thumbnail. Find them with:
#
#   grep -rn 'image:.*\.gif' *.qmd projects/*.qmd

set -u

DRY_RUN=0
KEEP_GIF=1
TARGET=""

for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN=1 ;;
        --keep-gif) KEEP_GIF=1 ;;
		--to-mp4)   KEEP_GIF=0 ;;
        -*)         echo "Unknown option: $arg"; exit 1 ;;
        *)          TARGET="$arg" ;;
    esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
BACKUP="$ROOT/../originals"

TARGET="${TARGET:-images}"
TARGET="${TARGET%/}"

if [ ! -d "$TARGET" ]; then
    echo "Not a directory: $TARGET"
    echo "Give a path relative to the repo root, e.g. images/gallery"
    exit 1
fi

GIF_MIN=$((1 * 1024 * 1024))
MP4_MIN=$((5 * 1024 * 1024))
IMG_MIN=$((2 * 1024 * 1024))

VID_W=960
VID_FPS=20
VID_CRF=28
IMG_MAX=2000

# Only used with --keep-gif. Smaller and slower than the video settings,
# because a GIF pays for every frame and every colour.
GIF_W=640
GIF_FPS=12
GIF_COLORS=128

CONVERTED_GIFS=()
RENAMED=()
TOTAL_BEFORE=0
TOTAL_AFTER=0

need() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing: $1"
        echo "  ffmpeg:      sudo apt install ffmpeg"
        echo "  imagemagick: sudo apt install imagemagick"
        exit 1
    }
}
need ffmpeg
need identify
need convert

human() { numfmt --to=iec "$1" 2>/dev/null || echo "$1"; }
size_of() { stat -c%s "$1" 2>/dev/null || echo 0; }

backup() {
    [ "$DRY_RUN" = 1 ] && return
    mkdir -p "$BACKUP"
    cp --parents "$1" "$BACKUP/" 2>/dev/null
}

report() {
    printf '  %-46s %8s -> %8s\n' "$(basename "$1")" "$(human "$2")" "$(human "$3")"
    TOTAL_BEFORE=$((TOTAL_BEFORE + $2))
    TOTAL_AFTER=$((TOTAL_AFTER + $3))
}

# One encoder for everything with motion. Full length, no -t.
encode_video() {
    ffmpeg -y -loglevel error -i "$1" \
        -vf "fps=$VID_FPS,scale='min($VID_W,iw)':-2:flags=lanczos" \
        -c:v libx264 -pix_fmt yuv420p -crf $VID_CRF \
        -g $VID_FPS -keyint_min $VID_FPS -sc_threshold 0 \
        -movflags +faststart -an "$2" 2>/dev/null
}

# Re-encode a GIF as a GIF: fewer frames, narrower, palette built from
# the clip itself rather than the default web palette.
shrink_gif() {
    ffmpeg -y -loglevel error -i "$1" \
        -vf "fps=$GIF_FPS,scale='min($GIF_W,iw)':-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=$GIF_COLORS[p];[b][p]paletteuse=dither=bayer" \
        "$2" 2>/dev/null
}

echo "Scanning $ROOT/$TARGET"
[ "$DRY_RUN" = 1 ] && echo "DRY RUN: nothing will be changed."
[ "$KEEP_GIF" = 1 ] && echo "KEEP GIF: animated GIFs shrink in place, no MP4 conversion."
echo "Working on /mnt/c is slow. Copying images to the Linux side first"
echo "and back afterwards is typically three to five times faster."
echo

echo "Animated GIFs over $(human $GIF_MIN):"
found=0
while IFS= read -r -d '' f; do
    before=$(size_of "$f")
    found=1

    if [ "$KEEP_GIF" = 1 ]; then
        tmp="${f%.*}-tmp.gif"
        if [ "$DRY_RUN" = 1 ]; then
            printf '  %-46s %8s -> %spx gif\n' \
                "$(basename "$f")" "$(human "$before")" "$GIF_W"
            continue
        fi
        backup "$f"
        printf '  %-46s %8s ... ' "$(basename "$f")" "$(human "$before")"
        if shrink_gif "$f" "$tmp"; then
            after=$(size_of "$tmp")
            # A re-encode that came out larger is not worth keeping.
            if [ "$after" -gt 0 ] && [ "$after" -lt "$before" ]; then
                mv -f "$tmp" "$f"
                printf '%8s\n' "$(human "$after")"
                TOTAL_BEFORE=$((TOTAL_BEFORE + before))
                TOTAL_AFTER=$((TOTAL_AFTER + after))
            else
                rm -f "$tmp"
                printf 'no gain, kept original\n'
            fi
        else
            printf 'FAILED\n'
            rm -f "$tmp"
        fi
        continue
    fi

    out="${f%.*}.mp4"
    if [ "$DRY_RUN" = 1 ]; then
        printf '  %-46s %8s -> mp4\n' "$(basename "$f")" "$(human "$before")"
        CONVERTED_GIFS+=("$f|$out")
        continue
    fi
    backup "$f"
    printf '  %-46s %8s ... ' "$(basename "$f")" "$(human "$before")"
    if encode_video "$f" "$out"; then
        after=$(size_of "$out")
        rm -f "$f"
        printf '%8s\n' "$(human "$after")"
        TOTAL_BEFORE=$((TOTAL_BEFORE + before))
        TOTAL_AFTER=$((TOTAL_AFTER + after))
        CONVERTED_GIFS+=("$f|$out")
    else
        printf 'FAILED\n'
        rm -f "$out"
    fi
done < <(find "$TARGET" -type f -iname '*.gif' -size +$((GIF_MIN / 1024))k -print0 2>/dev/null)
[ "$found" = 0 ] && echo "  none"
echo

echo "Videos over $(human $MP4_MIN):"
found=0
while IFS= read -r -d '' f; do
    before=$(size_of "$f")
    tmp="${f%.*}-tmp.mp4"
    found=1
    if [ "$DRY_RUN" = 1 ]; then
        printf '  %-46s %8s -> re-encode\n' "$(basename "$f")" "$(human "$before")"
        continue
    fi
    backup "$f"
    printf '  %-46s %8s ... ' "$(basename "$f")" "$(human "$before")"
    if encode_video "$f" "$tmp"; then
        mv -f "$tmp" "$f"
        after=$(size_of "$f")
        printf '%8s\n' "$(human "$after")"
        TOTAL_BEFORE=$((TOTAL_BEFORE + before))
        TOTAL_AFTER=$((TOTAL_AFTER + after))
    else
        printf 'FAILED\n'
        rm -f "$tmp"
    fi
done < <(find "$TARGET" -type f -iname '*.mp4' -size +$((MP4_MIN / 1024))k -print0 2>/dev/null)
[ "$found" = 0 ] && echo "  none"
echo

# TIFFs are handled at any size, not just over the threshold: no browser
# displays TIFF, so a small one on the site is broken rather than merely
# heavy. Multi-page files would make ImageMagick write name-0.jpg,
# name-1.jpg and so on, so the first page is selected explicitly.
echo "TIFFs (any size):"
found=0
while IFS= read -r -d '' f; do
    before=$(size_of "$f")
    found=1
    out="${f%.*}.jpg"
    if [ "$DRY_RUN" = 1 ]; then
        printf '  %-46s %8s -> jpg\n' "$(basename "$f")" "$(human "$before")"
        RENAMED+=("$(basename "$f")|$(basename "$out")")
        continue
    fi
    backup "$f"
    if convert "${f}[0]" -resize "${IMG_MAX}x${IMG_MAX}>" -quality 85 -strip "$out" 2>/dev/null; then
        rm -f "$f"
        report "$f" "$before" "$(size_of "$out")"
        RENAMED+=("$(basename "$f")|$(basename "$out")")
    else
        echo "  FAILED: $f"
    fi
done < <(find "$TARGET" -type f \( -iname '*.tif' -o -iname '*.tiff' \) -print0 2>/dev/null)
[ "$found" = 0 ] && echo "  none"
echo

echo "Images over $(human $IMG_MIN):"
found=0
while IFS= read -r -d '' f; do
    before=$(size_of "$f")
    found=1
    lower=$(echo "${f##*.}" | tr 'A-Z' 'a-z')
    to_jpeg=0
    if [ "$lower" = "png" ]; then
        colors=$(identify -format '%k' "$f" 2>/dev/null || echo 0)
        [ "${colors:-0}" -gt 10000 ] && to_jpeg=1
    fi
    if [ "$DRY_RUN" = 1 ]; then
        if [ "$to_jpeg" = 1 ]; then
            printf '  %-46s %8s -> jpg\n' "$(basename "$f")" "$(human "$before")"
            RENAMED+=("$(basename "$f")|$(basename "${f%.*}.jpg")")
        else
            printf '  %-46s %8s -> %spx\n' "$(basename "$f")" "$(human "$before")" "$IMG_MAX"
        fi
        continue
    fi
    backup "$f"
    if [ "$to_jpeg" = 1 ]; then
        out="${f%.*}.jpg"
        if convert "$f" -resize "${IMG_MAX}x${IMG_MAX}>" -quality 85 -strip "$out" 2>/dev/null; then
            rm -f "$f"
            report "$f" "$before" "$(size_of "$out")"
            RENAMED+=("$(basename "$f")|$(basename "$out")")
        else
            echo "  FAILED: $f"
        fi
    else
        if convert "$f" -resize "${IMG_MAX}x${IMG_MAX}>" -strip "$f" 2>/dev/null; then
            report "$f" "$before" "$(size_of "$f")"
        else
            echo "  FAILED: $f"
        fi
    fi
done < <(find "$TARGET" -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) \
         -size +$((IMG_MIN / 1024))k -print0 2>/dev/null)
[ "$found" = 0 ] && echo "  none"
echo

if [ "$DRY_RUN" = 0 ] && [ "$TOTAL_BEFORE" -gt 0 ]; then
    echo "Total: $(human $TOTAL_BEFORE) -> $(human $TOTAL_AFTER)"
    echo "Originals kept in $BACKUP"
    echo
fi

if [ ${#RENAMED[@]} -gt 0 ]; then
    echo "Stills that changed extension. Run this:"
    echo
    printf '  sed -i'
    for r in "${RENAMED[@]}"; do
        printf " \\\\\n    -e 's/%s/%s/g'" \
            "$(echo "${r%%|*}" | sed 's/\./\\./g')" "${r##*|}"
    done
    printf ' \\\n    *.qmd projects/*.qmd\n\n'
    echo "  Also captions.txt if any of these are gallery files, and the"
    echo "  image: front matter field if any was a listing thumbnail."
    echo
fi

if [ ${#CONVERTED_GIFS[@]} -gt 0 ]; then
    echo "These GIFs are now MP4s and need a <video> tag instead of an image."
    echo "Find each reference with:"
    echo
    for g in "${CONVERTED_GIFS[@]}"; do
        echo "  grep -rn '$(basename "${g%%|*}")' *.qmd projects/*.qmd"
    done
    echo
    echo "If one of them turns up in an image: front matter field, it was a"
    echo "listing thumbnail. Restore it from $BACKUP and re-run with"
    echo "--keep-gif instead."
    echo
    echo "For a clip that should loop silently the way the GIF did:"
    echo
    echo '  <figure>'
    echo '  <a href="../images/PATH.mp4">'
    echo '  <video src="../images/PATH.mp4" autoplay loop muted playsinline></video>'
    echo '  </a>'
    echo '  <figcaption>Caption text.</figcaption>'
    echo '  </figure>'
    echo
    echo "For one someone would want to watch and scrub, drop the anchor and"
    echo "use controls instead. Its own fullscreen button does the job:"
    echo
    echo '  <video src="../images/PATH.mp4" controls preload="metadata"></video>'
    echo
    echo "Put src on the video element, not a <source> child. Quarto's"
    echo "resource scan often misses a nested source, and the file then"
    echo "never reaches docs/. Any video directory also needs a line under"
    echo "resources: in _quarto.yml."
    echo
    echo "Raw HTML needs a blank line before and after it in the .qmd."
    echo
    echo "Gallery files are generated, so edit scripts/update_gallery.py"
    echo "rather than gallery.qmd, then re-run it."
    echo
fi

echo "Anything in $TARGET still over 10 MB:"
find "$TARGET" -type f -size +10M \
     -printf '  %s %p\n' 2>/dev/null | sort -rn | numfmt --to=iec --field=1
	 
