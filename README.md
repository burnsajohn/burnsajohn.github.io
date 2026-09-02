# protistsystems.org

Quarto source for the Burns Lab site, deployed to GitHub Pages.

The site is rendered locally and the output in `docs/` is committed. There is no
build workflow on GitHub. A push to `main` deploys whatever is in `docs/` at that
moment, so an unrendered change will not appear.

---

## Day-to-day

Preview while working:

```bash
quarto preview
```

Live-reloads on save. Nothing is public until you push.

Publish:

```bash
quarto render
git add -A && git commit -m "Describe the change"
git push
```

`git add -A` stages from the repo root regardless of which directory you are
standing in. `git add .` only stages from the current directory down, which
silently stages nothing if you are inside `images/` or `scripts/`.

Live a minute or two after the push. If the page looks unchanged, hard refresh
with Ctrl+Shift+R before assuming the deploy failed.

Adding a paper: paste the BibTeX entry into `references.bib`, then render and
push. Do not edit `publications.qmd`.

---

## Settings that must stay as they are

Repo Settings → Pages:

- Source: **Deploy from a branch**
- Branch: **main**, folder **/docs**
- Custom domain: **www.protistsystems.org**
- Enforce HTTPS: ticked

The custom domain field clears itself if the site is ever unpublished, and the
HTTPS checkbox stays greyed out until the certificate reissues, which can take
up to an hour.

Pointing the source at `/ (root)` makes GitHub serve the README instead of the
site. That is the usual cause of the site suddenly showing this file.

---

## DNS

Set at Wix (Domains → three dots → Manage DNS Records):

| Type  | Host name | Value                   |
|-------|-----------|-------------------------|
| A     | *(blank)* | 185.199.108.153         |
| A     | *(blank)* | 185.199.109.153         |
| A     | *(blank)* | 185.199.110.153         |
| A     | *(blank)* | 185.199.111.153         |
| CNAME | www       | burnsajohn.github.io    |

Wix's own A and CNAME records for those hosts must be deleted. Leaving both sets
in place makes the site resolve intermittently to whichever answers first.

---

## File map

| File | What it does |
|---|---|
| `_quarto.yml` | Site config, nav, citation style, `output-dir: docs`, `lightbox: auto`, and the `resources` list. Add a page to `navbar` when you create one. |
| `theme.scss` | All styling. Palette and type variables at the top. |
| `references.bib` | The publications page. Do not edit `publications.qmd` itself. |
| `CNAME` | Tells GitHub the custom domain. Must match the Pages setting. Listed under `resources` so a render does not delete it. |
| `docs/` | Rendered output. Generated, committed, never edited by hand. |
| `images/`, `files/` | Figures and downloadables. Served at `/images/…` and `/files/…`. |
| `scripts/update_gallery.py` | Regenerates `gallery.qmd`. Edit the script, not the page. |
| `scripts/update_pubs.py` | Builds the publication listing from `references.bib`. |

---

## Gotchas worth remembering

**Case sensitivity.** WSL and Windows treat `Squid.webp` and `squid.webp` as the
same file. GitHub does not. An image that previews fine can 404 once deployed.

**Missing images.** To list every referenced image that is not on disk, from a
directory of project pages:

```bash
grep -rhoE '\.\./images/[^)"}]+' *.qmd | sort -u | while read f; do
  [ -e "${f#../}" ] || echo "MISSING: $f"
done
```

**Video files.** Quarto's resource scan reliably catches markdown image links,
less so a `src` on a raw `<video>` tag. Any video directory needs a line under
`resources:` in `_quarto.yml` or the files will not be copied into `docs/`.

**Video size.** Convert GIFs with `-crf 23` or higher and check the result. An
unconstrained encode can land above GitHub's 50 MB warning threshold, and once a
large file is in history the warning persists on every push.

**Raw HTML in a fenced div.** Pandoc gathers adjacent raw HTML blocks and link
lines into a single `<p>`, which becomes one flex or grid child instead of
several. The stylesheet handles this with `display: contents` on `.gallery > p`
and `display: flex` on `.video-pair p`. If a new layout stacks when it should sit
side by side, inspect the container and look for that paragraph before changing
anything else.

**Lightbox and manual links.** `lightbox: auto` only applies to images that are
block-level. An image wrapped in `[![](…)](…)` is inline, so it is skipped, and
its caption is dropped into the alt slot. Do not hand-wrap images in links. Use
`.nolightbox` on heroes and logos, where a lightbox is not wanted.

---

## Design notes

Palette and type are set as variables at the top of `theme.scss`, so both are
one-line changes.

The palette is taken from transmitted-light microscopy: a pale cold field,
ink-dark text, chlorophyll green for links, and a strontium-blue secondary that
appears only on hover and focus rings.

Headings are Newsreader, body text is Source Sans 3, and labels are IBM Plex
Mono. The mono labels and the small bracketed rule that precedes them are the one
repeated motif. It is a scale bar, the annotation every micrograph carries. It is
the only ornament in the design, which is what lets it stay legible as one.

For species names in italic without tagging each one, the `.taxon` span class is
defined: `[*Oophila amblystomatis*]{.taxon}`.

Layout classes available in `theme.scss`: `.figure-row` with `.figure-text` for a
figure beside a paragraph, `.figure-stack` for a pair in one column,
`.fig-half` with `.fig-left` for a floated figure, `.clear-right` to drop a block
below one, `.gallery` for the image grid, `.video-pair` for two videos side by
side, `.topic` for hairline-separated entries, and `.logo-block` with
`.logo-text` for funders.