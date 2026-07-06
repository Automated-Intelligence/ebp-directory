/* EBP Directory front-end: loads data/interventions.json, smart search + filters. */
(async function () {
  const $ = (id) => document.getElementById(id);

  let DATA;
  try {
    const resp = await fetch("data/interventions.json");
    if (!resp.ok) throw new Error(resp.status);
    DATA = await resp.json();
  } catch (e) {
    $("loaderr").style.display = "block";
    return;
  }

  const TIER_ORDER = ["not-supported", "caution", "listed", "experimental", "promising", "supported", "well-supported"];
  const tierRank = (t) => TIER_ORDER.indexOf(t);
  const TIER_LABELS = {
    "well-supported": "Well-supported",
    "supported": "Supported",
    "promising": "Promising",
    "experimental": "Experimental",
    "listed": "Listed (unrated)",
    "caution": "Caution",
    "not-supported": "Not supported",
  };
  const POP_LABELS = {
    "children-adolescents": "Children & adolescents",
    "adolescents": "Adolescents",
    "adults": "Adults",
  };
  const SOURCE_SHORT = {
    buffalo: "UB Social Work",
    ect: "Effective Child Therapy (Div 53)",
    div12: "APA Div 12",
    cebc: "CEBC",
  };
  const PROB_LABELS = DATA.problemLabels || {};
  const probLabel = (tag) => PROB_LABELS[tag] || tag;

  // Query keywords that imply a problem area -> auto-rank by evidence for it.
  // (parent/family deliberately excluded: usually means the modality.)
  const PROBLEM_SYNONYMS = {
    anxiety: "anxiety", anxious: "anxiety", phobia: "anxiety", panic: "anxiety", worry: "anxiety",
    depression: "depression", depressed: "depression", depressive: "depression",
    trauma: "trauma-ptsd", ptsd: "trauma-ptsd", abuse: "trauma-ptsd", maltreatment: "trauma-ptsd",
    ocd: "ocd", obsessive: "ocd", compulsive: "ocd", hoarding: "ocd",
    adhd: "adhd", attention: "adhd", hyperactivity: "adhd", inattention: "adhd",
    autism: "autism", asd: "autism",
    conduct: "behavior-problems", defiant: "behavior-problems", defiance: "behavior-problems",
    oppositional: "behavior-problems", aggression: "behavior-problems", anger: "behavior-problems",
    substance: "substance-use", drug: "substance-use", drugs: "substance-use",
    alcohol: "substance-use", addiction: "substance-use", opioid: "substance-use",
    eating: "eating-disorders", anorexia: "eating-disorders", bulimia: "eating-disorders",
    bipolar: "bipolar",
    schizophrenia: "psychosis-schizophrenia", psychosis: "psychosis-schizophrenia", psychotic: "psychosis-schizophrenia",
    borderline: "personality-disorders",
    suicide: "suicide-self-harm", suicidal: "suicide-self-harm", suicidality: "suicide-self-harm",
    insomnia: "sleep", sleep: "sleep",
    grief: "grief-loss", bereavement: "grief-loss",
    pain: "chronic-pain-health",
    tic: "tics", tics: "tics", tourette: "tics",
    enuresis: "elimination", encopresis: "elimination", bedwetting: "elimination",
    gambling: "gambling",
    marital: "relationship-couples", couples: "relationship-couples",
    bullying: "stress-coping", divorce: "stress-coping",
  };
  // multi-word phrases checked against the whole query
  const PROBLEM_PHRASES = [
    ["self harm", "suicide-self-harm"], ["self-harm", "suicide-self-harm"],
    ["self injury", "suicide-self-harm"], ["acting out", "behavior-problems"],
    ["eating disorder", "eating-disorders"], ["mood swings", "bipolar"],
  ];

  const QUICK_PROBLEMS = [
    "anxiety", "depression", "trauma-ptsd", "adhd",
    "behavior-problems", "autism", "substance-use", "suicide-self-harm",
  ];

  const items = DATA.interventions;
  items.forEach((i) => {
    i._name = i.name.toLowerCase();
    i._aka = i.aka.join(" | ").toLowerCase();
    i._blob = [
      i.name,
      i.aka.join(" "),
      i.problems.map((p) => p + " " + probLabel(p)).join(" "),
      i.modality,
      i.populations.map((p) => POP_LABELS[p] || p).join(" "),
      i.summary,
      i.evidence.map((e) => e.problem).join(" "),
    ]
      .join(" ")
      .toLowerCase();
  });

  const fuse = new Fuse(items, {
    keys: [
      { name: "name", weight: 0.6 },
      { name: "aka", weight: 0.4 },
    ],
    threshold: 0.35,
    ignoreLocation: true,
  });

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---- filter dropdowns ----
  const fill = (id, values, labels) => {
    const sel = $(id);
    values.forEach((v) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = labels ? labels[v] || v : v;
      sel.appendChild(o);
    });
  };
  const uniq = (fn) => [...new Set(items.flatMap(fn))].sort();
  fill("f-tier", TIER_ORDER.slice().reverse().filter((t) => items.some((i) => i.tier === t)), TIER_LABELS);
  fill(
    "f-problem",
    uniq((i) => i.problems).sort((a, b) => probLabel(a).localeCompare(probLabel(b))),
    PROB_LABELS
  );
  fill("f-population", uniq((i) => i.populations), POP_LABELS);
  fill("f-modality", uniq((i) => [i.modality]));
  fill("f-source", uniq((i) => i.sources), SOURCE_SHORT);

  // ---- quick problem chips ----
  $("chips").innerHTML = QUICK_PROBLEMS.filter((p) => items.some((i) => i.problems.includes(p)))
    .map((p) => `<button class="chip" data-prob="${esc(p)}">${esc(probLabel(p))}</button>`)
    .join("");

  function detectProblem(q) {
    const ql = q.toLowerCase();
    for (const [phrase, tag] of PROBLEM_PHRASES) if (ql.includes(phrase)) return tag;
    for (const t of ql.split(/\s+/)) if (PROBLEM_SYNONYMS[t]) return PROBLEM_SYNONYMS[t];
    return "";
  }

  function nameScore(i, q, tokens) {
    if (i._name === q || i.aka.some((a) => a.toLowerCase() === q)) return 5; // exact
    if (i._name.startsWith(q)) return 4;
    if (i._name.includes(q)) return 3;
    if (i._aka.includes(q)) return 3;
    if (tokens.every((t) => i._name.includes(t) || i._aka.includes(t))) return 2;
    return 1; // matched via blob only
  }

  // Attach contextual (per-problem) tier. filterOut=true drops items with no
  // evidence for the problem (dropdown); false keeps them ranked lower (query).
  function contextualize(list, prob, filterOut) {
    return list
      .map((i) => {
        const rows = i.evidence.filter((e) => (e.problemTags || []).includes(prob));
        if (!rows.length) {
          if (filterOut) return null;
          return { ...i, _ctxProb: "", _hasCtx: false };
        }
        const ctxTier = rows.map((e) => e.tier).reduce((a, b) => (tierRank(b) > tierRank(a) ? b : a));
        return {
          ...i,
          _ctxProb: prob,
          _hasCtx: true,
          _ctxTier: ctxTier,
          _ctxCaution: rows.some((e) => e.tier === "caution" || e.tier === "not-supported"),
        };
      })
      .filter(Boolean);
  }

  let state = { detected: "" };

  function currentList() {
    const q = $("q").value.trim();
    const tier = $("f-tier").value,
      probSel = $("f-problem").value,
      pop = $("f-population").value,
      mod = $("f-modality").value,
      src = $("f-source").value;

    let list = items;
    const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (q) {
      list = items.filter((i) => tokens.every((t) => i._blob.includes(t)));
      if (!list.length) list = fuse.search(q).map((r) => r.item);
    }
    if (pop) list = list.filter((i) => i.populations.includes(pop));
    if (mod) list = list.filter((i) => i.modality === mod);
    if (src) list = list.filter((i) => i.sources.includes(src));

    // Problem context: explicit dropdown wins; else inferred from the query.
    state.detected = "";
    const prob = probSel || (q ? detectProblem(q) : "");
    if (prob) {
      if (!probSel) state.detected = prob;
      list = contextualize(list, prob, Boolean(probSel));
    }

    const usedTier = (i) => (i._hasCtx ? i._ctxTier : i.tier);
    if (tier) list = list.filter((i) => usedTier(i) === tier);

    list = [...list].sort((a, b) => {
      if (q) {
        // Only a full-phrase name/aka match ("TF-CBT", "coping cat") should
        // outrank evidence tier; descriptive queries ("adolescent trauma")
        // rank by evidence, not by which names happen to contain the words.
        const strong = (i) => {
          const s = nameScore(i, q.toLowerCase(), tokens);
          return s >= 3 ? s : 0;
        };
        const ds = strong(b) - strong(a);
        if (ds) return ds;
      }
      if (prob && a._hasCtx !== b._hasCtx) return a._hasCtx ? -1 : 1;
      return (
        tierRank(usedTier(b)) - tierRank(usedTier(a)) ||
        b.sources.length - a.sources.length ||
        a.name.localeCompare(b.name)
      );
    });
    return list;
  }

  function evidenceRows(i) {
    let rows = i.evidence;
    if (i._ctxProb) {
      rows = [...rows].sort(
        (a, b) =>
          (b.problemTags || []).includes(i._ctxProb) - (a.problemTags || []).includes(i._ctxProb)
      );
    }
    return rows
      .map((e) => {
        const src = SOURCE_SHORT[e.source] || e.source;
        const link = e.archivedUrl || e.url;
        const archived = e.archivedAt
          ? ` <span style="color:var(--muted)">(archived ${e.archivedAt.slice(0, 4)})</span>`
          : "";
        return `<tr>
          <td>${esc(src)}${archived}</td>
          <td><span class="badge tier-${esc(e.tier)}">${esc(e.rating)}</span><br><span style="color:var(--muted)">${esc(e.ratingLabel || "")}</span></td>
          <td>${esc(e.problem || "")}</td>
          <td><a href="${esc(link)}" target="_blank" rel="noopener">source ↗</a></td>
        </tr>`;
      })
      .join("");
  }

  const tierTitle = (t) => esc(DATA.tierDefinitions?.[t] || "");

  function card(i) {
    const aka = i.aka.length ? `<span class="aka">${esc(i.aka.slice(0, 3).join(" · "))}</span>` : "";
    const ctx = i._hasCtx ? i._ctxProb : "";
    const shownTier = ctx ? i._ctxTier : i.tier;
    const shownCaution = ctx ? i._ctxCaution : i.cautionFlag;
    const tierBadge = ctx
      ? `<span class="badge tier-${esc(shownTier)}" title="${tierTitle(shownTier)}">${esc(TIER_LABELS[shownTier] || shownTier)} for ${esc(probLabel(ctx))}</span>` +
        (i.tier !== shownTier
          ? `<span class="badge outline" title="${tierTitle(i.tier)}">overall: ${esc(TIER_LABELS[i.tier] || i.tier)}</span>`
          : "")
      : `<span class="badge tier-${esc(shownTier)}" title="${tierTitle(shownTier)}">${esc(TIER_LABELS[shownTier] || shownTier)}</span>`;
    const caution = shownCaution
      ? `<span class="pill-caution">⚠ ${ctx ? `registry reports it does not work for ${esc(probLabel(ctx))}` : "mixed findings"} — see evidence</span>`
      : "";
    const cautionNote = shownCaution
      ? `<div class="caution-note">At least one registry reports mixed, null, or concerning findings for this intervention${ctx ? ` for <strong>${esc(probLabel(ctx))}</strong>` : ""} (possibly for a specific problem or population). Review the evidence rows below and follow the source links before relying on it.</div>`
      : "";
    const summary = i.summary ? `<p class="summary">${esc(i.summary)}</p>` : "";
    const probBadges = i.problems
      .map(
        (p) =>
          `<button class="badge prob${p === ctx ? " prob-active" : ""}" data-prob="${esc(p)}" title="Filter by ${esc(probLabel(p))}">${esc(probLabel(p))}</button>`
      )
      .join("");
    const links = i.links.length
      ? `<div class="links"><strong>Learn more:</strong> ` +
        i.links
          .slice(0, 4)
          .map((l) => `<a href="${esc(l)}" target="_blank" rel="noopener">${esc(new URL(l).hostname.replace("www.", ""))}</a>`)
          .join(" · ") +
        `</div>`
      : "";
    return `<div class="card" data-id="${esc(i.id)}">
      <h3>${esc(i.name)}${aka}${caution}</h3>
      <div class="badges">
        ${tierBadge}
        <span class="badge outline">${esc(i.modality)}</span>
        ${i.populations.map((p) => `<span class="badge outline">${esc(POP_LABELS[p] || p)}</span>`).join("")}
        ${i.sources.map((s) => `<span class="badge outline">${esc(SOURCE_SHORT[s] || s)}</span>`).join("")}
      </div>
      <div class="badges">${probBadges}</div>
      <div class="detail">
        ${cautionNote}
        ${summary}
        <div class="evwrap"><table class="evidence">
          <tr><th>Registry</th><th>Rating</th><th>Problem / population</th><th>Link</th></tr>
          ${evidenceRows(i)}
        </table></div>
        ${links}
      </div>
    </div>`;
  }

  // ---- URL state (shareable / bookmarkable searches) ----
  const FIELDS = { q: "q", tier: "f-tier", problem: "f-problem", population: "f-population", modality: "f-modality", registry: "f-source" };
  function saveState() {
    const p = new URLSearchParams();
    for (const [k, id] of Object.entries(FIELDS)) if ($(id).value) p.set(k, $(id).value);
    history.replaceState(null, "", p.toString() ? "#" + p.toString() : location.pathname);
  }
  function restoreState() {
    const p = new URLSearchParams(location.hash.slice(1));
    for (const [k, id] of Object.entries(FIELDS)) if (p.get(k)) $(id).value = p.get(k);
  }

  function anyActive() {
    return Object.values(FIELDS).some((id) => $(id).value);
  }

  let shown = 60;
  function render(reset = true) {
    if (reset) shown = 60;
    const list = currentList();
    const bits = [`${list.length} intervention${list.length === 1 ? "" : "s"}`];
    if (state.detected)
      bits.push(`ranked by evidence for <strong>${esc(probLabel(state.detected))}</strong> (detected from your search)`);
    if (anyActive()) bits.push(`<a href="#" id="clear">Clear all</a>`);
    $("count").innerHTML = bits.join(" · ");
    document.querySelectorAll("#chips .chip").forEach((c) => {
      c.classList.toggle("active", c.dataset.prob === $("f-problem").value);
    });
    $("results").innerHTML = list.length
      ? list.slice(0, shown).map(card).join("") +
        (list.length > shown
          ? `<div class="card" id="more" style="text-align:center;color:var(--accent)">Show more (${list.length - shown} remaining)</div>`
          : "")
      : `<div class="card" style="text-align:center;color:var(--muted)">No interventions match. Try fewer words, or <a href="#" id="clear2">clear all filters</a>.</div>`;
    saveState();
  }

  function clearAll() {
    Object.values(FIELDS).forEach((id) => ($(id).value = ""));
    render();
  }

  $("count").addEventListener("click", (ev) => {
    if (ev.target.id === "clear") {
      ev.preventDefault();
      clearAll();
    }
  });

  $("chips").addEventListener("click", (ev) => {
    const chip = ev.target.closest(".chip");
    if (!chip) return;
    $("f-problem").value = $("f-problem").value === chip.dataset.prob ? "" : chip.dataset.prob;
    render();
  });

  $("results").addEventListener("click", (ev) => {
    if (ev.target.id === "clear2") {
      ev.preventDefault();
      clearAll();
      return;
    }
    const pb = ev.target.closest(".badge.prob");
    if (pb) {
      $("f-problem").value = $("f-problem").value === pb.dataset.prob ? "" : pb.dataset.prob;
      render();
      return;
    }
    const more = ev.target.closest("#more");
    if (more) {
      shown += 60;
      render(false);
      return;
    }
    if (ev.target.closest("a") || ev.target.closest(".detail")) return;
    const c = ev.target.closest(".card");
    if (c) c.classList.toggle("open");
  });

  Object.values(FIELDS).forEach((id) => $(id).addEventListener("input", () => render()));

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "/" && document.activeElement !== $("q")) {
      ev.preventDefault();
      $("q").focus();
    }
  });

  const srcLines = Object.values(DATA.sources || {})
    .map((s) => `${s.sourceName} (retrieved ${s.scrapedAt})`)
    .join(" · ");
  $("foot").innerHTML = `
    <strong>${DATA.interventionCount} interventions · dataset generated ${esc(DATA.generated)}</strong><br>
    Tip: press <kbd>/</kbd> to jump to search. Hover a rating badge for the tier definition. Click any problem tag to filter by it. The URL updates as you search, so you can bookmark or share a filtered view.<br><br>
    Sources: ${esc(srcLines)}<br><br>
    This directory is a reference tool that aggregates and links to public evidence-based practice
    registries. It is not clinical advice, and ratings may lag the registries — always follow the
    source links for current details, and use professional judgment for individual clients.`;

  restoreState();
  render();
})();
