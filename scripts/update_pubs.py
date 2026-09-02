#!/usr/bin/env python3
"""
Regenerate publications.yml from a Google Scholar BibTeX export.

    python3 scripts/update_pubs.py scholar.bib

Scholar has no API and blocks scraping, so the export is manual. It takes about
thirty seconds, once or twice a year:

  1. Open your Scholar profile.
  2. Scroll to the bottom and click "Show more" until every paper is loaded.
     Scholar shows 20 at a time and the export only covers what is on screen.
  3. Tick the checkbox at the top of the list to select all.
  4. Export -> BibTeX. Save the file as scholar.bib in this directory.

Scholar's BibTeX is thin: abbreviated journal names, missing DOIs, occasional
mangled titles. So this script treats Scholar as the authority on WHICH papers
are yours, and Crossref as the authority on their metadata. Each entry is
matched to Crossref by title and first author, and the clean record wins where
one is found. Entries with no Crossref match fall back to Scholar's fields.

Any `image:` value already in publications.yml is preserved across runs.

Standard library only. No API keys, no packages to install.

Optional: --orcid 0000-0002-2348-8438 uses ORCID as the source instead.
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONTACT_EMAIL = "burnsajohn@gmail.com"   # identifies you to Crossref
SURNAME = "Burns"
GIVEN_INITIAL = "J"

# Papers from this year onward are filed as current lab work; anything
# earlier goes under "Earlier work" on the publications page. Change the
# year and re-run to move the boundary.
ERA_CUTOFF = 2015

# The cutoff is a blunt instrument. Anything listed here overrides it, keyed
# by DOI in lower case. Use "prior" for later papers that belong with the
# earlier work, "current" for the reverse.
ERA_OVERRIDES = {
    # Transcription and DNA damage work, published after the cutoff but
    # belonging with the earlier program.
    "10.1093/nar/gky110": "prior",   # Genetic instability, loop structures, 2018
    "10.1073/pnas.1721764115": "prior"   # O6-methylguanine and p53, 2018
}

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "publications.yml"

# Cover images live here. Any file whose stem matches an entry's slug is
# picked up automatically, so adding a figure is: save the file, re-run.
IMAGE_DIR = ROOT / "images" / "pubs"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

USER_AGENT = f"protistsystems.org publication list (mailto:{CONTACT_EMAIL})"
CROSSREF_DELAY = 0.2

# Scholar profiles collect these alongside real papers. Dropped unless you
# pass --keep-all.
JUNK_TITLE_PATTERNS = [
    r"^supplementa",
    r"^correction to",
    r"^erratum",
    r"^author correction",
    r"^publisher correction",
    r"^reply to",
    r"^manuscript title",   # Scholar sometimes indexes a submitted version
    r"^author response",    # eLife registers these under their own DOI
    r"^decision letter",
    r"^editor's evaluation",
    r"^peer review",
]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def get_json(url, tries=3):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == tries - 1:
                raise
        except Exception:
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# BibTeX parsing. Scholar's output is simple and regular, so a full parser is
# overkill, but brace nesting still has to be tracked properly.
# ---------------------------------------------------------------------------

LATEX = {
    r"\&": "&", r"\%": "%", r"\_": "_", r"\#": "#", r"\$": "$",
    r"\textendash": "-", r"\textemdash": "-", r"``": '"', r"''": '"',
}

ACCENTS = {
    '\\"a': "ä", '\\"o': "ö", '\\"u': "ü", "\\'a": "á", "\\'e": "é",
    "\\'i": "í", "\\'o": "ó", "\\'u": "ú", "\\`a": "à", "\\`e": "è",
    "\\^a": "â", "\\^e": "ê", "\\^o": "ô", "\\~n": "ñ", "\\c c": "ç",
    "\\v s": "š", "\\v c": "č", "\\o": "ø", "\\aa": "å", "\\ss": "ß",
}


def clean_latex(text):
    if not text:
        return ""
    for k, v in ACCENTS.items():
        text = text.replace("{" + k + "}", v).replace(k, v)
    for k, v in LATEX.items():
        text = text.replace(k, v)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_bibtex(text):
    """Yield dicts of field -> value for each @entry in a BibTeX file."""
    entries = []
    i = 0
    while True:
        at = text.find("@", i)
        if at == -1:
            break
        brace = text.find("{", at)
        if brace == -1:
            break
        entry_type = text[at + 1:brace].strip().lower()

        # Walk forward tracking brace depth to find the end of this entry.
        depth, j = 0, brace
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        body = text[brace + 1:j]
        i = j + 1

        # First comma separates the citation key from the fields.
        comma = body.find(",")
        if comma == -1:
            continue
        fields_text = body[comma + 1:]

        fields = {"__type__": entry_type}
        k = 0
        while k < len(fields_text):
            eq = fields_text.find("=", k)
            if eq == -1:
                break
            name = fields_text[k:eq].strip().strip(",").lower()
            v = eq + 1
            while v < len(fields_text) and fields_text[v] in " \t\n":
                v += 1
            if v >= len(fields_text):
                break
            if fields_text[v] == "{":
                d, w = 0, v
                while w < len(fields_text):
                    if fields_text[w] == "{":
                        d += 1
                    elif fields_text[w] == "}":
                        d -= 1
                        if d == 0:
                            break
                    w += 1
                value = fields_text[v + 1:w]
                k = w + 1
            elif fields_text[v] == '"':
                w = fields_text.find('"', v + 1)
                value = fields_text[v + 1:w]
                k = w + 1
            else:
                w = v
                while w < len(fields_text) and fields_text[w] not in ",\n":
                    w += 1
                value = fields_text[v:w]
                k = w
            if name:
                fields[name] = clean_latex(value)
            nxt = fields_text.find(",", k)
            k = (nxt + 1) if nxt != -1 else len(fields_text)

        if fields.get("title"):
            entries.append(fields)
    return entries


def bib_authors(raw):
    """Split a BibTeX author field into [(family, given), ...]."""
    out = []
    for part in re.split(r"\s+and\s+", raw or ""):
        part = part.strip()
        if not part:
            continue
        # BibTeX marks a truncated author list with a literal "and others".
        if part.lower().rstrip(".") in ("others", "et al"):
            out.append(("et al.", ""))
            continue
        if "," in part:
            family, given = part.split(",", 1)
        else:
            bits = part.split()
            family, given = (bits[-1], " ".join(bits[:-1])) if bits else (part, "")
        out.append((family.strip(), given.strip()))
    return out


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

def crossref_by_doi(doi):
    data = get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    return data.get("message") if data else None


def crossref_by_title(title, first_author=""):
    """Find a DOI from a title. Only accepts confident matches."""
    params = {"query.bibliographic": title, "rows": "5",
              "select": "DOI,title,author,container-title,issued,type,score"}
    if first_author:
        params["query.author"] = first_author
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    data = get_json(url)
    if not data:
        return None
    items = (data.get("message") or {}).get("items") or []
    want = normalize_title(title)

    # Publishers register separate DOIs for author responses, decision
    # letters, corrections and the like, and their titles are the paper's
    # title with a prefix. Those must never win a containment match.
    def is_satellite(t):
        return any(re.search(pat, t) for pat in JUNK_TITLE_PATTERNS)

    candidates = [(item, normalize_title((item.get("title") or [""])[0]))
                  for item in items]

    # Exact match first, so a real record always beats a near one.
    for item, got in candidates:
        if got == want and not is_satellite(got):
            return item

    # Then containment, for Scholar's truncated titles.
    for item, got in candidates:
        if is_satellite(got):
            continue
        if len(want) > 25 and (want in got or got in want):
            return item
    return None


def normalize_title(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def same_work(a, b, floor=6, jaccard=0.82):
    """True if two normalized titles are almost certainly the same paper.

    Scholar duplicates typically differ by an inserted parenthetical or a
    missing subtitle, so exact and substring matching both fail. Comparing
    word sets catches those. The floor keeps short titles from colliding.
    """
    if a == b:
        return True
    wa, wb = set(a.split()), set(b.split())
    if len(wa) < floor or len(wb) < floor:
        return False
    if wa <= wb or wb <= wa:
        return True
    return len(wa & wb) / len(wa | wb) >= jaccard


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def format_authors_crossref(authors):
    out = []
    for a in authors:
        family = (a.get("family") or "").strip()
        given = (a.get("given") or "").strip()
        if not family:
            name = (a.get("name") or "").strip()
            if name:
                out.append(name)
            continue
        initials = "".join(p[0] for p in re.split(r"[\s\-.]+", given) if p)
        entry = f"{family} {initials}".strip()
        if family == SURNAME and initials.startswith(GIVEN_INITIAL):
            entry = f"**{entry}**"
        out.append(entry)
    if len(out) > 8:
        out = out[:8] + ["et al."]
    return ", ".join(out)


def format_authors_bib(pairs):
    out = []
    for family, given in pairs:
        if family == "et al.":
            out.append("et al.")
            continue
        initials = "".join(p[0] for p in re.split(r"[\s\-.]+", given) if p)
        entry = f"{family} {initials}".strip()
        if family == SURNAME and initials.startswith(GIVEN_INITIAL):
            entry = f"**{entry}**"
        out.append(entry)
    if len(out) > 8:
        out = out[:8] + ["et al."]
    return ", ".join(out)


def year_of(msg):
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return 0


def find_cover(slug):
    """Return a web path if images/pubs/<slug>.<ext> exists, else None."""
    for ext in IMAGE_EXTS:
        if (IMAGE_DIR / f"{slug}{ext}").exists():
            return f"images/pubs/{slug}{ext}"
    return None


def slugify(title, year):
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    words = [w for w in re.split(r"[^a-z0-9]+", text) if w]
    stop = {"a", "an", "the", "of", "in", "on", "for", "and", "is", "to",
            "from", "with", "by", "as", "at", "that", "are", "not"}
    keep = [w for w in words if w not in stop][:4]
    return f"{year}-{'-'.join(keep)}" if keep else str(year or "undated")


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------

def q(value):
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return '"' + re.sub(r"\s+", " ", s.replace("\n", " ")).strip() + '"'


def existing_images(path):
    """Keep image assignments across runs, keyed on DOI and on title."""
    if not path.exists():
        return {}, {}
    by_doi, by_title = {}, {}
    doi = title = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*-?\s*title:\s*"(.*)"\s*$', line)
        if m:
            title, doi = m.group(1), None
        m = re.match(r'\s*doi:\s*"?([^"\s]+)"?', line)
        if m:
            doi = m.group(1).lower()
        m = re.match(r'\s*image:\s*(.+)', line)
        if m:
            val = m.group(1).strip().strip('"')
            if val and val.lower() not in ("~", "null"):
                if doi:
                    by_doi[doi] = val
                if title:
                    by_title[normalize_title(title)] = val
    return by_doi, by_title


# ---------------------------------------------------------------------------

def load_from_bib(path, keep_all):
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    entries = parse_bibtex(raw)
    if not entries:
        sys.exit(f"No BibTeX entries found in {path}. Is it the right file?")

    kept, dropped = [], []
    seen = set()
    for e in entries:
        title = e.get("title", "")
        key = normalize_title(title)
        if key in seen:
            dropped.append(("duplicate", title))
            continue
        seen.add(key)
        if not keep_all and any(re.search(p, key) for p in JUNK_TITLE_PATTERNS):
            dropped.append(("looks like errata/supplement", title))
            continue
        kept.append(e)

    if dropped:
        print(f"  skipped {len(dropped)} entries:", file=sys.stderr)
        for why, t in dropped:
            print(f"    - [{why}] {t[:70]}", file=sys.stderr)
        print("    (pass --keep-all to include them)", file=sys.stderr)
    return kept


def load_from_orcid(orcid_id):
    data = get_json(f"https://pub.orcid.org/v3.0/{orcid_id}/works")
    if not data:
        sys.exit(f"Could not read ORCID record {orcid_id}.")
    out = []
    for group in data.get("group", []):
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        title = ((summaries[0].get("title") or {}).get("title") or {}).get("value", "")
        doi = ""
        for s in summaries:
            for eid in (s.get("external-ids") or {}).get("external-id", []):
                if eid.get("external-id-type", "").lower() == "doi":
                    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "",
                                 (eid.get("external-id-value") or "").strip().lower())
                    break
            if doi:
                break
        if title:
            out.append({"title": title, "doi": doi})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bibfile", nargs="?", default="scholar.bib",
                    help="Google Scholar BibTeX export (default: scholar.bib)")
    ap.add_argument("--orcid", metavar="ID",
                    help="use an ORCID iD as the source instead of a .bib file")
    ap.add_argument("--keep-all", action="store_true",
                    help="do not drop errata, corrections, or supplements")
    ap.add_argument("--no-crossref", action="store_true",
                    help="skip metadata lookup and use the .bib fields as-is")
    args = ap.parse_args()

    if args.orcid:
        print(f"Reading ORCID {args.orcid} ...")
        source = load_from_orcid(args.orcid)
    else:
        bib = Path(args.bibfile)
        if not bib.is_absolute():
            bib = ROOT / bib
        if not bib.exists():
            sys.exit(
                f"{bib} not found.\n\n"
                "Export it from Scholar: open your profile, click 'Show more'\n"
                "until every paper is loaded, tick the box at the top of the\n"
                "list to select all, then Export -> BibTeX. Save it as\n"
                f"{bib.name} in {ROOT}."
            )
        print(f"Reading {bib.name} ...")
        source = load_from_bib(bib, args.keep_all)

    print(f"  {len(source)} entries")

    by_doi, by_title = existing_images(OUTPUT)
    if by_doi or by_title:
        print(f"  preserving {len(set(by_doi) | set(by_title))} image assignment(s)")

    entries, unmatched = [], []
    for i, e in enumerate(source, 1):
        bib_title = e.get("title", "")
        print(f"  [{i}/{len(source)}] {bib_title[:56]:<56}", end="\r", flush=True)

        # .bib doi fields arrive in every shape: bare, prefixed with a
        # resolver URL, sometimes with stray leading whitespace inside the
        # braces. Normalise all of it before anything else touches the value.
        doi = (e.get("doi") or "").strip().strip("{}").strip().lower()
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi).strip()
        msg = None

        if not args.no_crossref:
            try:
                if doi:
                    msg = crossref_by_doi(doi)
                if msg is None:
                    authors = bib_authors(e.get("author", ""))
                    first = authors[0][0] if authors else ""
                    msg = crossref_by_title(bib_title, first)
                    if msg:
                        doi = (msg.get("DOI") or "").strip().lower()
            except Exception as exc:
                print(f"\n  warning: Crossref lookup failed for "
                      f"{bib_title[:50]} ({exc})", file=sys.stderr)
            time.sleep(CROSSREF_DELAY)

        # If a DOI resolved to a satellite record (author response, decision
        # letter, correction), fall back to the .bib metadata rather than
        # letting its title through.
        if msg and any(re.search(pat, normalize_title(
                strip_tags((msg.get("title") or [""])[0])))
                for pat in JUNK_TITLE_PATTERNS):
            msg = None

        if msg:
            title = strip_tags((msg.get("title") or [bib_title])[0])
            authors = format_authors_crossref(msg.get("author", []))
            journal = strip_tags((msg.get("container-title") or [""])[0])
            year = year_of(msg)
            kind = msg.get("type", "")
        else:
            unmatched.append(bib_title)
            title = bib_title
            authors = format_authors_bib(bib_authors(e.get("author", "")))
            journal = e.get("journal") or e.get("booktitle") or e.get("publisher", "")
            year = int(e.get("year")) if str(e.get("year", "")).isdigit() else 0
            kind = e.get("__type__", "")

        bits = [b for b in (authors, journal, str(year) if year else "") if b]
        slug = slugify(title, year)
        # A path already in the file wins, so a hand-set image with an odd
        # filename survives. Otherwise look for a file matching the slug.
        image = (by_doi.get(doi)
                 or by_title.get(normalize_title(title))
                 or find_cover(slug))

        entries.append({
            "title": title,
            "description": ". ".join(bits) + ("." if bits else ""),
            "path": f"https://doi.org/{doi}" if doi else (e.get("url") or ""),
            "doi": doi,
            "year": year,
            "image": image,
            "slug": slug,
            "preprint": kind == "posted-content",
        })

    # Second dedup pass. The first one runs on raw .bib titles, which misses
    # near-duplicates like "Manuscript Title: X" alongside "X". By this point
    # every entry has been through Crossref, so identical DOIs and identical
    # resolved titles are both reliable signals.
    # Richest first, so the copy that survives is the one with a DOI and a
    # journal name rather than a bare Scholar stub.
    def richness(e):
        return (bool(e["doi"]), len(e["description"]), e["year"])

    seen_doi, kept_titles, deduped, dropped = set(), [], [], []
    for e in sorted(entries, key=richness, reverse=True):
        key_doi = e["doi"] or None
        key_title = normalize_title(e["title"])

        if key_doi and key_doi in seen_doi:
            dropped.append(e["title"])
            continue

        # Scholar often holds two records of one paper whose titles differ by
        # an inserted parenthetical or a dropped subtitle. Substring matching
        # misses those, because the extra words can sit anywhere, so compare
        # word sets instead: one title's words being a subset of another's, or
        # the two overlapping heavily, means the same work.
        if any(same_work(key_title, k) for k in kept_titles):
            dropped.append(e["title"])
            continue

        if key_doi:
            seen_doi.add(key_doi)
        kept_titles.append(key_title)
        deduped.append(e)
    if dropped:
        print(f"\n  merged {len(dropped)} duplicate(s) after lookup:",
              file=sys.stderr)
        for t in dropped:
            print(f"    - {t[:72]}", file=sys.stderr)
    entries = deduped

    entries.sort(key=lambda x: (-x["year"], x["title"].lower()))

    lines = [
        "# Generated by scripts/update_pubs.py. Do not edit by hand.",
        "#",
        "# To give a paper a cover image, save it as images/pubs/<slug>.jpg",
        "# using the slug shown above the entry, then re-run. It is picked up",
        "# automatically and the paper moves into the grid.",
        "",
    ]
    for e in entries:
        lines.append(f"# image slug: {e['slug']}")
        lines.append(f"- title: {q(e['title'])}")
        lines.append(f"  description: {q(e['description'])}")
        if e["path"]:
            lines.append(f"  path: {q(e['path'])}")
        if e["doi"]:
            lines.append(f"  doi: {q(e['doi'])}")
        lines.append(f"  year: {e['year']}")
        era = ERA_OVERRIDES.get(e["doi"],
                                "current" if e["year"] >= ERA_CUTOFF else "prior")
        lines.append(f"  era: {era}")
        if e["image"]:
            lines.append(f"  image: {q(e['image'])}")
            # Entries with a cover image are promoted to the grid on the
            # publications page; the rest fall into the table below it.
            lines.append("  featured: true")
        if e["preprint"]:
            lines.append('  categories: ["Preprint"]')
        lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    print(" " * 78, end="\r")
    print(f"Wrote {len(entries)} entries to {OUTPUT.name}")

    if unmatched:
        print(f"\n{len(unmatched)} entries had no Crossref match and kept "
              f"Scholar's metadata:", file=sys.stderr)
        for t in unmatched:
            print(f"  - {t[:72]}", file=sys.stderr)
        print("Usually book chapters, theses, or preprints. Check the journal "
              "name and year on these.", file=sys.stderr)

    n_prior = sum(1 for e in entries if e["year"] < ERA_CUTOFF)
    if n_prior:
        print(f"{n_prior} entries dated before {ERA_CUTOFF} filed as earlier work.")

    dois_present = {e["doi"] for e in entries if e["doi"]}
    applied = [d for d in ERA_OVERRIDES if d in dois_present]
    unused = [d for d in ERA_OVERRIDES if d not in dois_present]
    if applied:
        print(f"{len(applied)} era override(s) applied.")
    if unused:
        print("Era overrides that matched nothing (check the DOI):",
              file=sys.stderr)
        for d in unused:
            print(f"  - {d}", file=sys.stderr)

    found = sum(1 for e in entries if e["image"])
    missing = len(entries) - found
    print(f"{found} with a cover image (grid), {missing} without (table).")
    if missing:
        print("To promote a paper, save its figure as "
              "images/pubs/<slug>.jpg using the slug shown")
        print("above the entry, then re-run. No editing required.")


if __name__ == "__main__":
    main()