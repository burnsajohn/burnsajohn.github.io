# protistsystems.org

Quarto source for the Burns Lab site, deployed to GitHub Pages.

Everything marked `TODO` is a placeholder. The structure and styling are done;
the content is yours to write.

---

## First-time setup

**1. Install Quarto** — <https://quarto.org/docs/get-started/>. One installer,
no dependency chain. Confirm with `quarto --version`.

**2. Preview locally.** From this directory:

```bash
quarto preview
```

This opens a browser and live-reloads on save. Work here until it looks right.
Nothing is public yet.

**3. Create the repository.** On GitHub, make a new **public** repo. The name
doesn't matter since you're using a custom domain — `protistsystems` is fine.
Then:

```bash
git init
git add .
git commit -m "Initial site"
git branch -M main
git remote add origin https://github.com/YOURUSERNAME/protistsystems.git
git push -u origin main
```

**4. Publish once from your machine.** This creates the `gh-pages` branch that
the automated workflow expects to exist:

```bash
quarto publish gh-pages
```

**5. Point GitHub Pages at it.** Repo Settings → Pages → set Source to *Deploy
from a branch*, branch `gh-pages`, folder `/ (root)`.

**6. Set the custom domain.** Same Settings → Pages screen, enter
`www.protistsystems.org`. Then in Wix DNS (Domains → three dots → Manage DNS
Records) set:

| Type  | Host name | Value                        |
|-------|-----------|------------------------------|
| A     | *(blank)* | 185.199.108.153              |
| A     | *(blank)* | 185.199.109.153              |
| A     | *(blank)* | 185.199.110.153              |
| A     | *(blank)* | 185.199.111.153              |
| CNAME | www       | YOURUSERNAME.github.io       |

Delete the existing Wix A and CNAME records for those hosts first — leaving both
sets in place will make the site resolve intermittently to whichever answers.

**7. Wait for the certificate.** Once DNS resolves, tick *Enforce HTTPS* on the
Pages settings screen. It can take up to an hour for the certificate to issue;
the checkbox stays greyed out until then.

---

## Day-to-day

Adding a paper:

```bash
# paste the BibTeX entry into references.bib, then
git add references.bib && git commit -m "Add 2026 paper" && git push
```

The workflow in `.github/workflows/publish.yml` renders and deploys on every
push to `main`. Nothing else to run.

Editing a page: the `.qmd` files are Markdown with a YAML header. Same syntax
you already use in R Markdown.

---

## File map

| File | What it does |
|---|---|
| `_quarto.yml` | Site config, nav, citation style. Add a page to `navbar` when you create one. |
| `theme.scss` | All styling. Palette and type variables at the top of the file. |
| `references.bib` | The publications page. Do not edit `publications.qmd` itself. |
| `CNAME` | Tells GitHub the custom domain. Must match the Pages setting. |
| `images/`, `files/` | Figures and downloadables. Served at `/images/…` and `/files/…`. |

---

## Design notes

Palette and type are set as variables at the top of `theme.scss`, so both are
one-line changes.

The palette is taken from transmitted-light microscopy — a pale cold field,
ink-dark text, chlorophyll green for links, and a strontium-blue secondary that
appears only on hover and focus rings.

Headings are Newsreader, body text is Source Sans 3, and labels are IBM Plex
Mono. The mono labels and the small bracketed rule that precedes them are the
one repeated motif: it's a scale bar, which is the annotation every micrograph
carries. It's the only ornament in the design, which is what lets it stay
legible as one.

If you want species names in italic without tagging each one, the `.taxon` span
class is defined: `[*Oophila amblystomatis*]{.taxon}`.

---

## If you'd rather not use Quarto

The same content works under plain Jekyll or Hugo with minimal changes — the
`.qmd` files are Markdown underneath. Quarto is the suggestion because it
handles the BibTeX publication list natively and because you're already in that
toolchain.
