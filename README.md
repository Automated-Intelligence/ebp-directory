# EBP Directory

A searchable directory of **evidence-based therapies and interventions** for therapists and social workers, cross-referenced from major public registries. One dataset, two front doors:

- **Web app** (`web/`) — instant search + filters by problem, population, modality, and evidence tier
- **MCP server** (`mcp-server/`) — the same data served to any MCP-capable LLM (Claude Desktop, Claude Code, ...)

**870 interventions · 1,011 registry ratings · 4 sources** (as of the date in `data/interventions.json`).

## Why

The registries already exist, but they're fragmented and use incompatible rating scales — the same intervention appears in four places with four different labels. This project normalizes them into one **crosswalk**: each intervention keeps every registry's original rating (with a provenance link), plus a normalized evidence tier so results are comparable at a glance.

## Data sources

| Key | Registry | What it rates |
|---|---|---|
| `div12` | [APA Division 12 / Society of Clinical Psychology](https://societyofclinicalpsychology.org/resource/psychological-treatments/) | Adult psychotherapies (Strong/Modest research support, classic Chambless criteria). Retrieved from Internet Archive snapshots — the society is migrating to a new Tolin-criteria system; each record carries its snapshot date. |
| `ect` | [Effective Child Therapy (APA Div 53 / SCCAP)](https://effectivechildtherapy.org/) | Child & adolescent treatments per disorder, five-level scale ("Works Well" ... "Tested and Does Not Work") |
| `cebc` | [California Evidence-Based Clearinghouse for Child Welfare](https://www.cebc4cw.org/) | Child-welfare-relevant programs, Scientific Rating 1–5 |
| `buffalo` | [UB School of Social Work EBP list](https://socialwork.buffalo.edu/continuing-education/training-registration/EBP-mental-health/evidence-based-practices/ebp-interventions.html) | Curated intervention list by modality and disorder (no formal scale) |

### Normalized evidence tiers

Grounded in the APA Division 12 / Chambless criteria (see Royse, *Program Evaluation: An Introduction to an Evidence-Based Approach*, ch. 1):

| Tier | Meaning | Maps from |
|---|---|---|
| `well-supported` | Multiple rigorous RCTs by independent teams | Div 12 "Strong", CEBC 1, SCCAP Level 1 |
| `supported` | At least one strong RCT or several smaller trials | Div 12 "Modest", CEBC 2, SCCAP Level 2 |
| `promising` | Some positive evidence | CEBC 3, SCCAP Level 3 |
| `experimental` | Untested / insufficient evidence | SCCAP Level 4 |
| `listed` | On a curated EBP list, unrated | Buffalo, CEBC NR |
| `caution` | Registry flags concerning/mixed findings | CEBC 5, Div 12 "Controversial" |
| `not-supported` | Tested; evidence fails to show effect | CEBC 4, SCCAP Level 5 |

An intervention's headline tier is its **best** rating; a ⚠ caution flag appears if *any* registry reports mixed/null/concerning findings (often for a specific problem or population — read the evidence rows).

## Run the web app

```bash
npm run serve
# open http://localhost:8321
```

Or push to GitHub with Pages enabled — `.github/workflows/deploy-pages.yml` publishes `web/` automatically.

## Hook up the MCP server

```bash
cd mcp-server && npm install
```

Claude Desktop (`claude_desktop_config.json`) or any MCP client:

```json
{
  "mcpServers": {
    "ebp-directory": {
      "command": "node",
      "args": ["C:\\Users\\above\\ebp-directory\\mcp-server\\index.js"]
    }
  }
}
```

Claude Code: `claude mcp add ebp-directory -- node C:\Users\above\ebp-directory\mcp-server\index.js`

Tools: `search_interventions` (query + tier/problem/population/modality/registry filters), `get_intervention` (full evidence with provenance links), `list_filters`.

## Keeping it up to date

Every entry carries the registry's rating, a source URL, and the retrieval date — staleness is visible, never silent, and the registries remain the source of truth.

- **Manual:** `python scripts/refresh.py` re-scrapes everything, rebuilds the dataset, and writes a reviewable diff to `data/CHANGES.md` (added/removed interventions, tier changes). Review, then commit.
- **Automated:** `.github/workflows/refresh-data.yml` runs quarterly and opens a PR with the change report as its body. Nothing merges without human review — "CEBC downgraded this program" should always get eyeballs.
- A guardrail fails the refresh if the new dataset shrinks >30% (a scraper silently breaking should never wipe the data).

### Pipeline

```
scrapers/scrape_*.py   -> data/sources/<registry>.json   (raw per-registry records)
scrapers/build_dataset.py -> data/interventions.json     (merged crosswalk)
                          -> web/data/interventions.json (copy the app loads)
```

Merging is by normalized name plus an alias table (`ALIASES` / `CANONICAL_NAMES` in `build_dataset.py`) — e.g. "TF-CBT", "Trauma-Focused CBT", and "Trauma-Focused Cognitive-Behavioral Therapy" are one entry. To fix a bad merge or add an alias, edit those tables and run `npm run build-data`.

## Roadmap (Tier 2 sources)

- **SAMHSA EBP Resource Center** — blocks non-browser fetches; needs a browser-automation pass
- **Title IV-E Prevention Services Clearinghouse**, **Blueprints**, **HomVEE**, **The Community Guide**, **WSIPP** (effect sizes + benefit-cost ratios)
- VA/DoD and NICE guideline recommendations as evidence citations

## Disclaimer

This is a reference tool that aggregates and links to public registries. It is **not clinical advice**. Ratings reflect the retrieval dates recorded in the dataset and may lag the registries. Registry descriptions are not reproduced wholesale; entries link to the authoritative source. Use professional judgment for individual clients.
