"""Refresh the dataset from all sources and report what changed.

Usage:
    python scripts/refresh.py            # fresh scrape + diff report
    python scripts/refresh.py --cached   # rebuild from cached pages (fast, for testing)

Never auto-publishes: it rewrites data/ and prints/writes a human-reviewable
change report (data/CHANGES.md). Review the diff, then commit.
"""
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPERS = ["scrape_buffalo.py", "scrape_ect.py", "scrape_div12.py", "scrape_cebc.py"]
DATA = os.path.join(ROOT, "data", "interventions.json")
PAGE_CACHE = os.path.join(ROOT, "scrapers", "cache", "pages")


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def index_by_id(dataset):
    return {i["id"]: i for i in dataset["interventions"]} if dataset else {}


def evidence_key(i):
    return sorted((e["source"], e.get("rating", ""), e.get("problem", "")) for e in i["evidence"])


def main():
    cached = "--cached" in sys.argv
    old = load(DATA)

    if not cached and os.path.isdir(PAGE_CACHE):
        shutil.rmtree(PAGE_CACHE)  # force fresh fetches
    # Div12 URL list also comes from a CDX query; refresh it too.
    div12_urls = os.path.join(ROOT, "scrapers", "cache", "div12-old-urls.txt")
    if not cached and os.path.exists(div12_urls):
        os.remove(div12_urls)

    failures = []
    for s in SCRAPERS:
        print(f"== {s}")
        r = subprocess.run([sys.executable, s], cwd=os.path.join(ROOT, "scrapers"))
        if r.returncode != 0:
            failures.append(s)
    if failures:
        print(f"WARNING: {failures} failed — existing source files for those registries are reused.")

    subprocess.run([sys.executable, "build_dataset.py"], cwd=os.path.join(ROOT, "scrapers"), check=True)

    new = load(DATA)
    old_ix, new_ix = index_by_id(old), index_by_id(new)

    added = sorted(set(new_ix) - set(old_ix))
    removed = sorted(set(old_ix) - set(new_ix))
    tier_changes, evidence_changes = [], []
    for iid in set(old_ix) & set(new_ix):
        o, n = old_ix[iid], new_ix[iid]
        if o["tier"] != n["tier"]:
            tier_changes.append((iid, o["tier"], n["tier"]))
        elif evidence_key(o) != evidence_key(n):
            evidence_changes.append(iid)

    lines = [
        f"# Dataset refresh — {time.strftime('%Y-%m-%d')}",
        "",
        f"Interventions: {len(old_ix)} -> {len(new_ix)}",
        f"- Added: {len(added)}",
        f"- Removed: {len(removed)}",
        f"- Tier changes: {len(tier_changes)}",
        f"- Evidence detail changes: {len(evidence_changes)}",
        f"- Scraper failures: {failures or 'none'}",
        "",
    ]
    if added:
        lines += ["## Added"] + [f"- {new_ix[i]['name']} ({new_ix[i]['tier']})" for i in added] + [""]
    if removed:
        lines += ["## Removed (verify against the registry before accepting!)"] + [
            f"- {old_ix[i]['name']} (was {old_ix[i]['tier']})" for i in removed
        ] + [""]
    if tier_changes:
        lines += ["## Tier changes"] + [f"- {new_ix[i]['name']}: {a} -> {b}" for i, a, b in tier_changes] + [""]
    if evidence_changes:
        lines += ["## Evidence detail changes"] + [f"- {new_ix[i]['name']}" for i in evidence_changes] + [""]

    report = "\n".join(lines)
    with open(os.path.join(ROOT, "data", "CHANGES.md"), "w", encoding="utf-8") as f:
        f.write(report)
    print("\n" + report)

    # Guardrail: a mostly-empty scrape should never silently replace the dataset.
    if old and len(new_ix) < 0.7 * len(old_ix):
        print("ERROR: new dataset is >30% smaller than the old one — likely a scraper broke.")
        print("Data files were rewritten; review 'git diff' carefully or 'git checkout -- data/'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
