#!/usr/bin/env python3
"""Merge all batch-NN-output.json files into a single _analyses_merged.json,
indexed by src_rel for fast lookup."""

import glob
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).resolve().parent.parent  # Learning root (this script lives in _Tools/)
OUT = BASE / '_Curated'

merged: dict[str, dict] = {}
duplicates_seen = []

for path in sorted(glob.glob(str(OUT / '_analysis' / 'batch-*-output.json'))):
    data = json.load(open(path, encoding='utf-8'))
    for rec in data:
        rel = rec['src_rel']
        if rel in merged:
            duplicates_seen.append(rel)
            continue
        merged[rel] = rec

print(f'Merged {len(merged)} unique records')
if duplicates_seen:
    print(f'WARN: {len(duplicates_seen)} src_rel collisions:')
    for r in duplicates_seen:
        print(f'  - {r}')

# Sanity check: every file in _manifest.json should have an analysis
manifest = json.load(open(OUT / '_manifest.json', encoding='utf-8'))
manifest_rels = {m['src_rel'] for m in manifest}
analysis_rels = set(merged.keys())

missing = manifest_rels - analysis_rels
extra = analysis_rels - manifest_rels

if missing:
    print(f'\nMISSING analyses for {len(missing)} files:')
    for r in sorted(missing):
        print(f'  - {r}')
if extra:
    print(f'\nEXTRA analyses for {len(extra)} files (not in manifest):')
    for r in sorted(extra):
        print(f'  - {r}')

(OUT / '_analyses_merged.json').write_text(
    json.dumps(merged, indent=2, ensure_ascii=False),
    encoding='utf-8',
)
print(f'\nWrote {OUT / "_analyses_merged.json"}')
