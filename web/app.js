/* EBP Directory front-end: loads data/interventions.json, fuzzy search + filters. */
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

  const items = DATA.interventions;
  // Precompute a searchable text blob per intervention for multi-word AND search.
  items.forEach((i) => {
    i._blob = [
      i.name,
      i.aka.join(" "),
      i.problems.join(" "),
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

  function search(q) {
    // Every word must appear somewhere in the item (name, problems, ratings...);
    // fall back to fuzzy name search for typos.
    const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
    const hits = items.filter((i) => tokens.every((t) => i._blob.includes(t)));
    return hits.length ? hits : fuse.search(q).map((r) => r.item);
  }

  // ---- filters ----
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
  fill("f-tier", Object.keys(TIER_LABELS).filter((t) => items.some((i) => i.tier === t)), TIER_LABELS);
  fill("f-problem", uniq((i) => i.problems));
  fill("f-population", uniq((i) => i.populations), POP_LABELS);
  fill("f-modality", uniq((i) => [i.modality]));
  fill("f-source", uniq((i) => i.sources), SOURCE_SHORT);

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function currentList() {
    const q = $("q").value.trim();
    let list = q ? search(q) : items;
    const tier = $("f-tier").value,
      prob = $("f-problem").value,
      pop = $("f-population").value,
      mod = $("f-modality").value,
      src = $("f-source").value;
    if (pop) list = list.filter((i) => i.populations.includes(pop));
    if (mod) list = list.filter((i) => i.modality === mod);
    if (src) list = list.filter((i) => i.sources.includes(src));

    if (prob) {
      // Problem filter: only interventions with evidence FOR that problem, and
      // rank/badge them by their rating for that problem — an intervention
      // that's well-supported for schizophrenia but "does not work" for ADHD
      // must not top the ADHD list.
      list = list
        .map((i) => {
          const rows = i.evidence.filter((e) => (e.problemTags || []).includes(prob));
          if (!rows.length) return null;
          const ctxTier = rows.map((e) => e.tier).reduce((a, b) => (tierRank(b) > tierRank(a) ? b : a));
          const ctxCaution = rows.some((e) => e.tier === "caution" || e.tier === "not-supported");
          return { ...i, _ctxTier: ctxTier, _ctxCaution: ctxCaution, _ctxProb: prob };
        })
        .filter(Boolean)
        .sort(
          (a, b) =>
            tierRank(b._ctxTier) - tierRank(a._ctxTier) ||
            b.sources.length - a.sources.length ||
            a.name.localeCompare(b.name)
        );
    }
    if (tier) list = list.filter((i) => (i._ctxTier || i.tier) === tier);
    return list;
  }

  function evidenceRows(i) {
    let rows = i.evidence;
    if (i._ctxProb) {
      // matching-problem rows first
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

  function card(i) {
    const aka = i.aka.length ? `<span class="aka">${esc(i.aka.slice(0, 3).join(" · "))}</span>` : "";
    // With a problem filter active, the headline badge is the rating FOR that
    // problem; the overall tier moves to a secondary outline badge.
    const ctx = i._ctxProb;
    const shownTier = ctx ? i._ctxTier : i.tier;
    const shownCaution = ctx ? i._ctxCaution : i.cautionFlag;
    const tierBadge = ctx
      ? `<span class="badge tier-${esc(shownTier)}">${esc(TIER_LABELS[shownTier] || shownTier)} for ${esc(ctx)}</span>` +
        (i.tier !== shownTier
          ? `<span class="badge outline">overall: ${esc(TIER_LABELS[i.tier] || i.tier)}</span>`
          : "")
      : `<span class="badge tier-${esc(shownTier)}">${esc(TIER_LABELS[shownTier] || shownTier)}</span>`;
    const caution = shownCaution
      ? `<span class="pill-caution">⚠ ${ctx ? `registry reports it does not work for ${esc(ctx)}` : "mixed findings"} — see evidence</span>`
      : "";
    const cautionNote = shownCaution
      ? `<div class="caution-note">At least one registry reports mixed, null, or concerning findings for this intervention${ctx ? ` for <strong>${esc(ctx)}</strong>` : ""} (possibly for a specific problem or population). Review the evidence rows below and follow the source links before relying on it.</div>`
      : "";
    const summary = i.summary ? `<p class="summary">${esc(i.summary)}</p>` : "";
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

  let shown = 60;
  function render(reset = true) {
    if (reset) shown = 60;
    const list = currentList();
    $("count").textContent = `${list.length} intervention${list.length === 1 ? "" : "s"}`;
    $("results").innerHTML =
      list.slice(0, shown).map(card).join("") +
      (list.length > shown
        ? `<div class="card" id="more" style="text-align:center;color:var(--accent)">Show more (${list.length - shown} remaining)</div>`
        : "");
  }

  $("results").addEventListener("click", (ev) => {
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

  ["q", "f-tier", "f-problem", "f-population", "f-modality", "f-source"].forEach((id) =>
    $(id).addEventListener("input", () => render())
  );

  const srcLines = Object.values(DATA.sources || {})
    .map((s) => `${s.sourceName} (retrieved ${s.scrapedAt})`)
    .join(" · ");
  $("foot").innerHTML = `
    <strong>${DATA.interventionCount} interventions · dataset generated ${esc(DATA.generated)}</strong><br>
    Sources: ${esc(srcLines)}<br><br>
    This directory is a reference tool that aggregates and links to public evidence-based practice
    registries. It is not clinical advice, and ratings may lag the registries — always follow the
    source links for current details, and use professional judgment for individual clients.`;

  render();
})();
