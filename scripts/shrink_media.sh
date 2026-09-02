#!/usr/bin/env bash
#
# Shrink every oversized image and animation under images/ to web sizes.
#
#   bash scripts/shrink_media.sh --dry-run    # show what would change
#   bash scripts/shrink_media.sh              # do it
#
# Originals are copied to ../originals/ before anything is touched, so
# nothing is destroyed. That folder sits outside the repo.
#
#   animated GIF -> MP4, 960px wide, FULL LENGTH, faststart for seeking
#   large MP4    -> re-encoded, 960px wide, full length
#   large PNG    -> JPEG if photographic, resized if line art
#   large JPEG   -> resized to 2000px on the long edge
#
# Nothing is truncated. Clips keep their full duration.

set -u

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
BACKUP="$ROOT/../originals"

GIF_MIN=$((1 * 1024 * 1024))
MP4_MIN=$((5 * 1024 * 1024))
IMG_MIN=$((2 * 1024 * 1024))

VID_W=960
VID_FPS=20
VID_CRF=28
IMG_MAX=2000

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

echo "Scanning $ROOT/images"
[ "$DRY_RUN" = 1 ] && echo "DRY RUN: nothing will be changed."
echo "Working on /mnt/c is slow. Copying images to the Linux side first"
echo "and back afterwards is typically three to five times faster."
echo

echo "Animated GIFs over $(human $GIF_MIN):"
found=0
while IFS= read -r -d '' f; do
    before=$(size_of "$f")
    out="${f%.*}.mp4"
    found=1
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
done < <(find images -type f -iname '*.gif' -size +$((GIF_MIN / 1024))k -print0 2>/dev/null)
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
done < <(find images -type f -iname '*.mp4' -size +$((MP4_MIN / 1024))k -print0 2>/dev/null)
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
done < <(find images -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) \
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
fi

if [ ${#CONVERTED_GIFS[@]} -gt 0 ]; then
    echo "These GIFs are now MP4s and need a <video> tag instead of an image."
    echo "Find each reference with:"
    echo
    for g in "${CONVERTED_GIFS[@]}"; do
        echo "  grep -rn '$(basename "${g%%|*}")' *.qmd projects/*.qmd"
    done
    echo
    echo "For a clip that should loop silently the way the GIF did:"
    echo
    echo '  <video autoplay loop muted playsinline>'
    echo '    <source src="../images/PATH.mp4" type="video/mp4">'
    echo '  </video>'
    echo
    echo "For one someone would want to watch and scrub:"
    echo
    echo '  <video controls preload="metadata">'
    echo '    <source src="../images/PATH.mp4" type="video/mp4">'
    echo '  </video>'
    echo
    echo "Raw HTML needs a blank line before and after it in the .qmd."
    echo
fi

echo "Anything still over 10 MB:"
find . -path ./.git -prune -o -path ./docs -prune -o -type f -size +10M \
     -printf '  %s %p\n' 2>/dev/null | sort -rn | numfmt --to=iec --field=1
	 
