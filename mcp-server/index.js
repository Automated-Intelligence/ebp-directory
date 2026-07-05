#!/usr/bin/env node
/**
 * EBP Directory MCP server.
 *
 * Exposes the same data/interventions.json the web app uses, so any
 * MCP-capable LLM client (Claude Desktop, Claude Code, etc.) can search
 * evidence-based therapies/interventions with provenance.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const DATA = JSON.parse(readFileSync(join(ROOT, "data", "interventions.json"), "utf-8"));

const SOURCE_NAMES = Object.fromEntries(
  Object.entries(DATA.sources).map(([k, v]) => [k, v.sourceName])
);

// Precompute search blobs (same approach as the web app).
for (const i of DATA.interventions) {
  i._blob = [
    i.name,
    i.aka.join(" "),
    i.problems.join(" "),
    i.modality,
    i.populations.join(" "),
    i.summary,
    i.evidence.map((e) => e.problem).join(" "),
  ]
    .join(" ")
    .toLowerCase();
}

function compact(i) {
  return {
    id: i.id,
    name: i.name,
    aka: i.aka,
    modality: i.modality,
    tier: i.tier,
    cautionFlag: i.cautionFlag,
    problems: i.problems,
    populations: i.populations,
    registries: i.sources.map((s) => SOURCE_NAMES[s] || s),
    summary: i.summary ? i.summary.slice(0, 200) : undefined,
  };
}

function searchItems({ query, tier, problem, population, modality, source }) {
  let list = DATA.interventions;
  if (query) {
    const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
    list = list.filter((i) => tokens.every((t) => i._blob.includes(t)));
  }
  if (tier) list = list.filter((i) => i.tier === tier);
  if (problem) list = list.filter((i) => i.problems.includes(problem));
  if (population) list = list.filter((i) => i.populations.includes(population));
  if (modality) list = list.filter((i) => i.modality.toLowerCase().includes(modality.toLowerCase()));
  if (source) list = list.filter((i) => i.sources.includes(source));
  return list;
}

const server = new McpServer({ name: "ebp-directory", version: "1.0.0" });

server.tool(
  "search_interventions",
  "Search the evidence-based therapy/intervention directory (aggregated from SAMHSA-adjacent registries: APA Division 12, Effective Child Therapy/Div 53, CEBC, UB School of Social Work). " +
    "Returns matching interventions with normalized evidence tiers. " +
    "Tiers, best first: well-supported, supported, promising, experimental, listed, caution, not-supported. " +
    "Use get_intervention for full per-registry evidence and links.",
  {
    query: z.string().optional().describe("Free-text search: therapy name, problem, population (e.g. 'adolescent trauma')"),
    tier: z.enum(["well-supported", "supported", "promising", "experimental", "listed", "caution", "not-supported"]).optional(),
    problem: z.string().optional().describe("Problem tag, e.g. 'anxiety', 'trauma-ptsd', 'substance-use' (see list_filters)"),
    population: z.enum(["children-adolescents", "adolescents", "adults"]).optional(),
    modality: z.string().optional().describe("Modality substring, e.g. 'CBT', 'Family'"),
    source: z.enum(["buffalo", "ect", "div12", "cebc"]).optional().describe("Restrict to one registry"),
    limit: z.number().int().min(1).max(100).optional().describe("Max results (default 20)"),
  },
  async (args) => {
    const list = searchItems(args);
    const limit = args.limit ?? 20;
    const out = {
      total: list.length,
      showing: Math.min(limit, list.length),
      interventions: list.slice(0, limit).map(compact),
    };
    return { content: [{ type: "text", text: JSON.stringify(out, null, 1) }] };
  }
);

server.tool(
  "get_intervention",
  "Get one intervention's full record: every registry rating with provenance links, summary, aliases, and caution flags. Look up by id (from search results) or name.",
  {
    idOrName: z.string().describe("Intervention id (e.g. 'trauma-focused-cognitive-behavioral-therapy') or name (e.g. 'TF-CBT')"),
  },
  async ({ idOrName }) => {
    const q = idOrName.toLowerCase().trim();
    const hit =
      DATA.interventions.find((i) => i.id === q) ||
      DATA.interventions.find((i) => i.name.toLowerCase() === q) ||
      DATA.interventions.find((i) => i.aka.some((a) => a.toLowerCase() === q)) ||
      DATA.interventions.find((i) => i._blob.includes(q));
    if (!hit) {
      return { content: [{ type: "text", text: `No intervention found for "${idOrName}". Try search_interventions.` }] };
    }
    const { _blob, ...rest } = hit;
    rest.disclaimer =
      "Aggregated reference data — not clinical advice. Ratings were retrieved on the dates in the dataset and may lag the registries; follow the source URLs for current details.";
    return { content: [{ type: "text", text: JSON.stringify(rest, null, 1) }] };
  }
);

server.tool(
  "list_filters",
  "List available filter values (problem tags, tiers with definitions, modalities, populations, registries) plus dataset metadata (sources, retrieval dates, counts).",
  {},
  async () => {
    const uniq = (fn) => [...new Set(DATA.interventions.flatMap(fn))].sort();
    const out = {
      generated: DATA.generated,
      interventionCount: DATA.interventionCount,
      tierDefinitions: DATA.tierDefinitions,
      problems: uniq((i) => i.problems),
      populations: uniq((i) => i.populations),
      modalities: uniq((i) => [i.modality]),
      registries: DATA.sources,
    };
    return { content: [{ type: "text", text: JSON.stringify(out, null, 1) }] };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`EBP Directory MCP server ready — ${DATA.interventionCount} interventions (dataset ${DATA.generated})`);
