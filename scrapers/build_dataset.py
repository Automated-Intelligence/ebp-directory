"""Merge per-source scrape files into data/interventions.json.

The crosswalk: the same intervention appears in multiple registries under
slightly different names with incompatible rating scales. We merge by
normalized name (plus a manual alias table), keep every registry's rating as
an `evidence` entry with provenance, and compute a normalized tier from the
best rating (per the Chambless/Div-12 criteria described in Royse, *Program
Evaluation*, ch. 1).
"""
import json
import os
import re
import time

from common import ROOT, SOURCES_DIR

OUT = os.path.join(ROOT, "data", "interventions.json")

# ---------------------------------------------------------------- name canon

# Every key is a normalized name string; the value is the canonical group id.
ALIASES = {
    "tf cbt": "trauma-focused-cognitive-behavioral-therapy",
    "trauma focused cbt": "trauma-focused-cognitive-behavioral-therapy",
    "trauma focused cognitive behavioral therapy": "trauma-focused-cognitive-behavioral-therapy",
    "trauma focused cognitive behavior therapy": "trauma-focused-cognitive-behavioral-therapy",
    "dbt": "dialectical-behavior-therapy",
    "dialectical behavior therapy": "dialectical-behavior-therapy",
    "dialectical behaviour therapy": "dialectical-behavior-therapy",
    "emdr": "eye-movement-desensitization-and-reprocessing",
    "eye movement desensitization and reprocessing": "eye-movement-desensitization-and-reprocessing",
    "acceptance and commitment therapy": "acceptance-and-commitment-therapy",
    "parent child interaction therapy": "parent-child-interaction-therapy",
    "multisystemic therapy": "multisystemic-therapy",
    "functional family therapy": "functional-family-therapy",
    "interpersonal psychotherapy": "interpersonal-psychotherapy",
    "interpersonal therapy": "interpersonal-psychotherapy",
    "prolonged exposure": "prolonged-exposure-therapy",
    "prolonged exposure therapy": "prolonged-exposure-therapy",
    "prolonged exposure therapy for adolescents": "prolonged-exposure-therapy",
    "cognitive processing therapy": "cognitive-processing-therapy",
    "motivational interviewing": "motivational-interviewing",
    "cognitive behavioral therapy": "cognitive-behavioral-therapy",
    "cbt": "cognitive-behavioral-therapy",
    "behavioral activation": "behavioral-activation",
    "exposure and response prevention": "exposure-and-response-prevention",
    "exposure and ritual prevention": "exposure-and-response-prevention",
    "coping cat": "coping-cat",
    "incredible years": "the-incredible-years",
    "the incredible years": "the-incredible-years",
    "triple p": "triple-p-positive-parenting-program",
    "triple p positive parenting program": "triple-p-positive-parenting-program",
    "cbits": "cognitive-behavioral-intervention-for-trauma-in-schools",
    "cognitive behavioral intervention for trauma in schools": "cognitive-behavioral-intervention-for-trauma-in-schools",
}


# Preferred display names for aliased groups (otherwise longest name wins,
# which picks ugly variants like "CBT (individual, Non face-to-face CBT)").
CANONICAL_NAMES = {
    "trauma-focused-cognitive-behavioral-therapy": "Trauma-Focused Cognitive Behavioral Therapy (TF-CBT)",
    "dialectical-behavior-therapy": "Dialectical Behavior Therapy (DBT)",
    "eye-movement-desensitization-and-reprocessing": "Eye Movement Desensitization and Reprocessing (EMDR)",
    "acceptance-and-commitment-therapy": "Acceptance and Commitment Therapy (ACT)",
    "parent-child-interaction-therapy": "Parent-Child Interaction Therapy (PCIT)",
    "multisystemic-therapy": "Multisystemic Therapy (MST)",
    "functional-family-therapy": "Functional Family Therapy (FFT)",
    "interpersonal-psychotherapy": "Interpersonal Psychotherapy (IPT)",
    "prolonged-exposure-therapy": "Prolonged Exposure Therapy (PE)",
    "cognitive-processing-therapy": "Cognitive Processing Therapy (CPT)",
    "motivational-interviewing": "Motivational Interviewing (MI)",
    "cognitive-behavioral-therapy": "Cognitive Behavioral Therapy (CBT)",
    "behavioral-activation": "Behavioral Activation (BA)",
    "exposure-and-response-prevention": "Exposure and Response Prevention (ERP)",
    "the-incredible-years": "The Incredible Years",
    "triple-p-positive-parenting-program": "Triple P – Positive Parenting Program",
    "cognitive-behavioral-intervention-for-trauma-in-schools": "Cognitive Behavioral Intervention for Trauma in Schools (CBITS)",
}


def norm(name):
    s = name.lower()
    s = re.sub(r"\[.*?\]", " ", s)
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slugify(name):
    s = norm(name)
    return re.sub(r"\s+", "-", s)[:80].strip("-")


def canon_id(name):
    n = norm(name)
    return ALIASES.get(n) or slugify(name)


def extract_acronym(name):
    m = re.search(r"\(([A-Z][A-Za-z0-9+&./ -]{1,20})\)", name)
    return m.group(1) if m else ""


# ------------------------------------------------------------- problem tags

PROBLEM_TAGS = [
    ("anxiety", r"anxiety|anxious|panic|phobia|selective mutism|worry|fear"),
    ("depression", r"depress|sadness|hopeless|mood|dysthymi"),
    ("trauma-ptsd", r"trauma|ptsd|post traumatic|abuse|maltreat|neglect"),
    ("ocd", r"obsess|compulsi|ocd|hoarding|body focused repetitive"),
    ("adhd", r"adhd|attention deficit|hyperactiv|inattention|problems focusing"),
    ("autism", r"autism|asd|developmental disorder"),
    ("behavior-problems", r"conduct|disruptive|defian|oppositional|acting out|rule.?breaking|behavioral challenge|behavior problem|aggress|anger"),
    ("substance-use", r"substance|drug|alcohol|smoking|opioid|addiction"),
    ("eating-disorders", r"eating|anorexi|bulimi|binge|body image"),
    ("bipolar", r"bipolar|mood swings"),
    ("psychosis-schizophrenia", r"schizophreni|psychosis|psychotic"),
    ("personality-disorders", r"borderline|personality disorder"),
    ("suicide-self-harm", r"suicid|self.?injur|self.?harm"),
    ("sleep", r"insomnia|sleep"),
    ("grief-loss", r"grief|loss|bereave|death"),
    ("chronic-pain-health", r"pain|headache|migraine|fibromyalgia|health|illness|obesity|overweight"),
    ("parenting-family", r"parent|family|attachment|foster|adopt|caregiver|home visit"),
    ("child-welfare", r"child welfare|placement|reunification|kinship"),
    ("school", r"school|academic|classroom|learning"),
    ("tics", r"\btics?\b|tourette"),
    ("elimination", r"enuresis|encopresis|elimination|toilet|bed.?wetting"),
    ("gambling", r"gambling"),
    ("gender-identity", r"gender dysphoria|lgbt"),
    ("relationship-couples", r"couple|marital|intimate partner|domestic violence"),
    ("stress-coping", r"stress|coping|resilien|adjust|divorce|natural disaster|bullying"),
]


PROBLEM_LABELS = {
    "anxiety": "Anxiety & Phobias",
    "depression": "Depression & Mood",
    "trauma-ptsd": "Trauma & PTSD",
    "ocd": "OCD & Related",
    "adhd": "ADHD & Attention",
    "autism": "Autism Spectrum",
    "behavior-problems": "Behavior Problems & Conduct",
    "substance-use": "Substance Use",
    "eating-disorders": "Eating Disorders",
    "bipolar": "Bipolar Spectrum",
    "psychosis-schizophrenia": "Psychosis & Schizophrenia",
    "personality-disorders": "Personality Disorders",
    "suicide-self-harm": "Suicide & Self-Harm",
    "sleep": "Sleep Problems",
    "grief-loss": "Grief & Loss",
    "chronic-pain-health": "Chronic Pain & Physical Health",
    "parenting-family": "Parenting & Family",
    "child-welfare": "Child Welfare",
    "school": "School-Based Concerns",
    "tics": "Tics & Tourette",
    "elimination": "Elimination Disorders",
    "gambling": "Gambling",
    "gender-identity": "Gender Identity",
    "relationship-couples": "Couples & Relationships",
    "stress-coping": "Stress & Coping",
}


def tag_problems(*texts):
    blob = " ".join(t.lower() for t in texts if t)
    return [tag for tag, pat in PROBLEM_TAGS if re.search(pat, blob)]


# ------------------------------------------------------------------- tiers

TIER_ORDER = ["not-supported", "caution", "listed", "experimental", "promising", "supported", "well-supported"]


def tier_rank(t):
    return TIER_ORDER.index(t) if t in TIER_ORDER else 0


def evidence_tier(source, rating):
    r = (rating or "").strip()
    if source == "div12":
        if r.startswith("Strong"):
            return "well-supported"
        if r.startswith("Modest"):
            return "supported"
        if r.startswith("Controversial"):
            return "caution"
        return "listed"
    if source == "cebc":
        return {"1": "well-supported", "2": "supported", "3": "promising",
                "4": "not-supported", "5": "caution", "NR": "listed"}.get(r, "listed")
    if source == "ect":
        return {"1": "well-supported", "2": "supported", "3": "promising",
                "4": "experimental", "5": "not-supported"}.get(r, "listed")
    return "listed"  # buffalo: inclusion == curated as evidence-based, unrated


# ---------------------------------------------------------------- modality

MODALITY_RULES = [
    ("CBT", r"cognitive.?behav|cbt|coping cat|coping power|cognitive processing|cognitive therapy"),
    ("Exposure Therapy", r"exposure|response prevention|flooding|systematic desensitization"),
    ("EMDR", r"emdr|eye movement"),
    ("DBT", r"dialectical"),
    ("ACT / Mindfulness", r"acceptance and commitment|mindfulness|meditation"),
    ("Family Therapy", r"family|multisystemic|attachment.?based"),
    ("Parent Training", r"parent|incredible years|triple p"),
    ("Play Therapy", r"play therapy|theraplay"),
    ("Interpersonal Therapy", r"interpersonal"),
    ("Psychodynamic Therapy", r"psychodynamic|psychoanaly"),
    ("Behavior Therapy", r"behavio|contingency|reinforcement|token"),
    ("Motivational Interviewing", r"motivational"),
    ("Group Intervention", r"\bgroup\b"),
    ("School-Based", r"school"),
    ("Psychoeducation", r"psychoeducation|education"),
]


def infer_modality(name, buffalo_modality=""):
    if buffalo_modality:
        return buffalo_modality
    n = name.lower()
    for label, pat in MODALITY_RULES:
        if re.search(pat, n):
            return label
    return "Other / Multi-component"


# ------------------------------------------------------------------- merge


def load(source):
    p = os.path.join(SOURCES_DIR, source + ".json")
    if not os.path.exists(p):
        print(f"WARNING: {p} missing, skipping")
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_group(groups, name):
    gid = canon_id(name)
    if gid not in groups:
        groups[gid] = {
            "id": gid, "name": name, "aka": set(), "modality": "",
            "problems": set(), "populations": set(), "evidence": [],
            "summary": "", "links": set(),
        }
    g = groups[gid]
    if gid in CANONICAL_NAMES:
        if g["name"] != CANONICAL_NAMES[gid]:
            g["aka"].add(g["name"])
            g["name"] = CANONICAL_NAMES[gid]
        if name != g["name"]:
            g["aka"].add(name)
    elif len(name) > len(g["name"]):
        g["aka"].add(g["name"])
        g["name"] = name
    elif name != g["name"]:
        g["aka"].add(name)
    ac = extract_acronym(name)
    if ac:
        g["aka"].add(ac)
    return g


def main():
    groups = {}
    sources_meta = {}

    buffalo = load("buffalo")
    if buffalo:
        sources_meta["buffalo"] = {k: buffalo[k] for k in ("sourceName", "baseUrl", "scrapedAt", "notes", "recordCount")}
        for r in buffalo["records"]:
            g = get_group(groups, r["name"])
            g["modality"] = g["modality"] or r["modality"]
            tags = tag_problems(r["problem"], r["note"], r["name"])
            g["problems"].update(tags)
            g["populations"].add("children-adolescents")
            g["links"].add(r["url"])
            g["evidence"].append({
                "source": "buffalo", "rating": "Listed",
                "ratingLabel": "Included on UB School of Social Work EBP list",
                "problem": r["problem"] + ((" — " + r["note"]) if r["note"] else ""),
                "problemTags": tags,
                "url": buffalo["baseUrl"], "tier": "listed",
            })

    ect = load("ect")
    if ect:
        sources_meta["ect"] = {k: ect[k] for k in ("sourceName", "baseUrl", "scrapedAt", "notes", "recordCount")}
        for r in ect["records"]:
            g = get_group(groups, r["name"])
            tags = tag_problems(r["problem"], r["name"])
            g["problems"].update(tags)
            g["populations"].add("children-adolescents")
            g["links"].add(r["url"])
            g["evidence"].append({
                "source": "ect", "rating": f"Level {r['level']}",
                "ratingLabel": r["levelLabel"],
                "problem": r["problem"] + ((f" ({r['ageGroup']})") if r["ageGroup"] else ""),
                "problemTags": tags,
                "url": r["url"], "tier": evidence_tier("ect", r["level"]),
            })

    div12 = load("div12")
    if div12:
        sources_meta["div12"] = {k: div12[k] for k in ("sourceName", "baseUrl", "scrapedAt", "notes", "recordCount")}
        for r in div12["records"]:
            g = get_group(groups, r["name"])
            tags = tag_problems(r["problem"], r["name"])
            g["problems"].update(tags)
            pop = "adolescents" if "adolescen" in r["fullTitle"].lower() else "adults"
            g["populations"].add(pop)
            g["links"].add(r["url"])
            if r["summary"] and len(r["summary"]) > len(g["summary"]):
                g["summary"] = r["summary"]
            g["evidence"].append({
                "source": "div12", "rating": r["rating"] or "Listed",
                "ratingLabel": r["rating"] or "On classic Div 12 EST list",
                "problem": r["problem"],
                "problemTags": tags,
                "url": r["url"], "archivedUrl": r["archivedUrl"],
                "archivedAt": r["archivedAt"],
                "tier": evidence_tier("div12", r["rating"]),
            })

    cebc = load("cebc")
    if cebc:
        sources_meta["cebc"] = {k: cebc[k] for k in ("sourceName", "baseUrl", "scrapedAt", "notes", "recordCount")}
        for r in cebc["records"]:
            if not r.get("rating"):
                continue  # skip unrated shells
            g = get_group(groups, r["name"])
            tags = tag_problems(r.get("topic", ""), r.get("targetPopulation", ""), r["name"])
            g["problems"].update(tags)
            g["populations"].add("children-adolescents")
            g["links"].add(r["url"])
            if r.get("summary") and len(r["summary"]) > len(g["summary"]):
                g["summary"] = r["summary"]
            g["evidence"].append({
                "source": "cebc", "rating": r["rating"],
                "ratingLabel": r["ratingLabel"],
                "problem": r.get("topic", "") or r.get("targetPopulation", "")[:120],
                "problemTags": tags,
                "url": r["url"], "tier": evidence_tier("cebc", r["rating"]),
            })

    interventions = []
    for g in groups.values():
        tiers = [e["tier"] for e in g["evidence"]]
        best = max(tiers, key=tier_rank)
        has_caution = any(t in ("caution", "not-supported") for t in tiers)
        interventions.append({
            "id": g["id"],
            "name": g["name"],
            "aka": sorted(g["aka"] - {g["name"]}),
            "modality": infer_modality(g["name"], g["modality"]),
            "problems": sorted(g["problems"]),
            "populations": sorted(g["populations"]),
            "tier": best,
            "cautionFlag": has_caution,
            "summary": g["summary"],
            "links": sorted(g["links"]),
            "evidence": g["evidence"],
            "sources": sorted({e["source"] for e in g["evidence"]}),
        })

    # Most corroborated first within each tier
    interventions.sort(key=lambda x: (-tier_rank(x["tier"]), -len(x["sources"]), x["name"].lower()))

    out = {
        "generated": time.strftime("%Y-%m-%d"),
        "tierDefinitions": {
            "well-supported": "Strongest evidence: multiple rigorous RCTs by independent teams (Div 12 'Strong', CEBC 1, SCCAP Level 1)",
            "supported": "Good evidence: at least one strong RCT or several smaller trials (Div 12 'Modest', CEBC 2, SCCAP Level 2)",
            "promising": "Some positive evidence, more research needed (CEBC 3, SCCAP Level 3)",
            "experimental": "Untested or insufficient evidence (SCCAP Level 4)",
            "listed": "Included on a curated EBP list without a formal rating",
            "caution": "A registry has flagged mixed/concerning findings — read the evidence entries",
            "not-supported": "Tested and evidence fails to demonstrate effect",
        },
        "problemLabels": PROBLEM_LABELS,
        "sources": sources_meta,
        "interventionCount": len(interventions),
        "interventions": interventions,
    }
    web_copy = os.path.join(ROOT, "web", "data", "interventions.json")
    os.makedirs(os.path.dirname(web_copy), exist_ok=True)
    for path in (OUT, web_copy):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"Merged {sum(len(g['evidence']) for g in groups.values())} evidence entries "
          f"into {len(interventions)} interventions -> {OUT}")
    from collections import Counter
    print(Counter(i["tier"] for i in interventions))


if __name__ == "__main__":
    main()
