# Learning

Personal learning library: source materials, and three generated views of them.

## Layout

| Folder / file | What it is |
|---|---|
| `Education/`, `Identity/`, `JScript/`, `Microsoft_Fullstack/`, `PythonLearning/`, `LearningWebbook.Maui/`, `Crystal/`, `CSharp-Projects-main/` | Source materials (courses, projects, notes) |
| `*.docx`, `Adding-New-Category.html` (root) | Loose source documents — **leave in root**: the curation manifest keys them by this location |
| `_Curated/` | **Generated** — the curated concept-guide site. Entry point: `_Curated/00-Index.html` |
| `_Organized/` | **Generated** — the categorised document site |
| `learning-webbook.html` | **Generated** — single-file webbook of everything |
| `_Tools/` | All generator scripts + QA screenshots. See `_Tools/README.md` for the pipelines |

Practice companion (separate repo): `CSharpProjects/GeneralExercises` — blank-page drill
docs whose INDEX cross-references `_Curated` and `_Organized` concept guides.

## Moving to another machine

Everything is portable as of 03/07/2026 — all scripts resolve paths relative to their own
location, and all generated HTML uses relative links.

1. Copy the whole `Learning` folder (or `git clone` — but note `.gitignore` excludes
   `Crystal/`, `CSharp-Projects-main/` and all QA screenshots, so a clone won't carry those).
2. Everything viewable works immediately: `_Curated`, `_Organized`, the webbook.
3. Before re-RUNNING the curation pipeline on the new machine, run
   `_Tools/_extract_for_curation.py` once — it refreshes the absolute paths baked into
   `_Curated/_manifest.json`. Details in `_Tools/README.md`.
