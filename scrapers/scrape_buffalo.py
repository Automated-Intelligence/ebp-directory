"""Scrape the University at Buffalo School of Social Work EBP intervention list.

Page structure: collapsible <h2> sections per modality (Behavior Therapy, CBT,
Family Therapy, ...). Inside each section, <p> blocks start with a disorder
name followed by <a> links to individual interventions, optionally with an
"-- also used to treat X" note after the link text.
"""
import re

from common import clean, fetch, save_source, strip_tags

URL = (
    "https://socialwork.buffalo.edu/continuing-education/training-registration/"
    "EBP-mental-health/evidence-based-practices/ebp-interventions.html"
)

SKIP_SECTIONS = {"Psychopharmacology Information"}
SKIP_LINK_TEXT = {"account login", "technical support", "american psychiatric association"}


def main():
    html = fetch(URL)
    if not html:
        raise SystemExit("could not fetch Buffalo page")

    # Split into collapsible sections; the title lives in the section's button.
    parts = re.split(r'<h2 id="collapsible', html)
    records = []
    for part in parts[1:]:
        m = re.search(r'<button class="collapsible-button"[^>]*>(.*?)</button>', part, re.S)
        if not m:
            continue
        section = strip_tags(m.group(1))
        section = re.sub(r"UBCMS.*$", "", section).strip()
        if not section or section in SKIP_SECTIONS:
            continue

        # Split on <p> starts: each chunk is "Disorder name" text followed by
        # intervention links (which may sit outside the closed </p>).
        body = part[part.find("collapsible-content"):] if "collapsible-content" in part else part
        problem = ""
        for block in re.split(r"<p[^>]*>", body)[1:]:
            block = block.split("<h2")[0]  # don't bleed into the next section
            first_a = block.find("<a ")
            lead = strip_tags(block[:first_a]) if first_a != 0 else ""
            lead = lead.strip(" ,;:")
            if lead and len(lead) < 120:
                problem = lead  # short leading text = new disorder heading
            links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
            for href, text in links:
                name = strip_tags(text).strip(" ,;")
                if not name or name.lower() in SKIP_LINK_TEXT:
                    continue
                # "Name -- also used to treat X" -> split the note off.
                note = ""
                nm = re.split(r"\s*[–—-]\s+", name, maxsplit=1)
                if len(nm) == 2 and len(nm[0]) > 3:
                    name, note = nm[0].strip(" ,;"), nm[1].strip()
                if len(name) < 3:
                    continue
                # the page sometimes leaves the closing paren outside the <a>
                if name.count("(") > name.count(")"):
                    name += ")"
                records.append(
                    {
                        "name": clean(name),
                        "url": href.strip(),
                        "modality": section,
                        "problem": clean(problem),
                        "note": clean(note),
                    }
                )

    save_source(
        "buffalo",
        "University at Buffalo School of Social Work – Evidence-Based Practices in Mental Health",
        URL,
        records,
        notes=(
            "Curated list of EBP interventions for children/adolescents and families, "
            "organized by modality and disorder. No formal rating scale; inclusion on "
            "the list indicates the intervention is considered evidence-based by the "
            "UB School of Social Work continuing-education program."
        ),
    )


if __name__ == "__main__":
    main()
