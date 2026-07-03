# _Tools

All the scripts that generate the Learning folder's three outputs live here. Everything uses
**relative path resolution** (`Path(__file__).resolve().parent.parent` = the Learning root),
so this whole Learning folder can be copied to another machine and the scripts keep working —
no path editing required.

## The three pipelines

### 1. Webbook — `build_webbook.py`
Builds `../learning-webbook.html`, a single self-contained HTML file from all Learning
resources. Run directly: `python build_webbook.py`.

### 2. Organized — `organize_learning.py`
Builds `../_Organized/` (the per-category concept-guide site). Also the shared library:
its extraction helpers (`discover_files`, `extract_docx_md`, `extract_pdf_pages`, ...) are
imported by the curation scripts below. Imports `build_webbook` itself — they must stay siblings.

### 3. Curated — three scripts, run in this order
1. `_extract_for_curation.py` — extracts plain text from all sources into
   `../_Curated/_extracted/`, writes `../_Curated/_manifest.json`.
2. *(analyst agents)* — read the extracts, write `../_Curated/_analysis/batch-NN-output.json`.
3. `_aggregate_analyses.py` — merges batches into `../_Curated/_analyses_merged.json`,
   sanity-checks against the manifest.
4. `render_curated.py` — renders the final `../_Curated/` site (hubs, category pages,
   per-doc pages with the curated overlay).

## After moving to another machine

- The rendered outputs (`_Curated/`, `_Organized/`, `learning-webbook.html`) are fully
  relative — they work immediately, no rebuild needed.
- `_Curated/_manifest.json` and `_analyses_merged.json` contain absolute paths (`src_abs`,
  `text_abs`) from the machine that generated them. They only matter when RE-RUNNING the
  pipeline: run `_extract_for_curation.py` once on the new machine before `render_curated.py`
  (analyses are keyed by relative path, so they survive).
- `__pycache__/` folders regenerate on first run — never copy them.

## Manual additions to _Curated (not pipeline-generated)

- `_Curated/CORE/language/csharp-operators-and-conversions.html` — hand-authored 03/07/2026;
  its card was hand-added to `_Category.html` (doc count bumped 10 → 11). If you re-run
  `render_curated.py`, check it doesn't overwrite `_Category.html` and drop that card.

## screenshots/

QA screenshots from building/verifying each output's design, sorted by pipeline
(`curated/`, `organized/`, `webbook/`). Git-ignored, historical reference only —
safe to delete if space matters.
