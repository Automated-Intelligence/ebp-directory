"""Scrape the California Evidence-Based Clearinghouse for Child Welfare (CEBC).

Program URLs come from the WordPress sitemap
(wp-sitemap-posts-cebc-program-1.xml, ~600 programs). Each program page shows
a Scientific Rating (1-5 or NR), a topic area, and a target population.
"""
import re

from common import clean, fetch, save_source, strip_tags

SITEMAP = "https://www.cebc4cw.org/wp-sitemap-posts-cebc-program-1.xml"

RATING_LABELS = {
    "1": "Well-Supported by Research Evidence",
    "2": "Supported by Research Evidence",
    "3": "Promising Research Evidence",
    "4": "Evidence Fails to Demonstrate Effect",
    "5": "Concerning Practice",
    "NR": "Not able to be Rated",
}


def parse_program(url, html):
    title_m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not title_m:
        return None
    name = re.split(r"\s*[–|-]\s*The California", strip_tags(title_m.group(1)))[0].strip()
    if not name or name.lower().startswith("page not found"):
        return None

    text = strip_tags(html)

    rating = ""
    rm = re.search(r"Scientific Rating\s*:?\s*(\d|NR)\b", text)
    if not rm:
        rm = re.search(r'Scientific\s*Rating[^0-9NR]{0,200}?\b(\d|NR)\b', text)
    if rm:
        rating = rm.group(1)

    topic = ""
    tm = re.search(r"Topic Area\(?s?\)?\s*:?\s*(.{3,120}?)(?:\s{2,}|Scientific Rating|About This)", text)
    if tm:
        topic = tm.group(1).strip(" :|")

    population = ""
    pm = re.search(r"Target Population\s*:?\s*(.{3,300}?)(?:\s*For children/adolescents ages|\s*For parents|\s*Brief Description|Program Overview|$)", text)
    if pm:
        population = pm.group(1).strip(" :|")

    ages = ""
    am = re.search(r"ages?\s*:?\s*(\d+\s*(?:–|-|to)\s*\d+)", text, re.I)
    if am:
        ages = am.group(1)

    desc = ""
    dm = re.search(r'<meta name="description" content="([^"]+)"', html)
    if dm:
        desc = clean(dm.group(1))[:500]

    return {
        "name": clean(name),
        "url": url,
        "rating": rating,
        "ratingLabel": RATING_LABELS.get(rating, ""),
        "topic": clean(topic),
        "targetPopulation": clean(population)[:300],
        "ages": ages,
        "summary": desc,
    }


def main():
    xml = fetch(SITEMAP, use_cache=False)
    if not xml:
        raise SystemExit("could not fetch CEBC sitemap")
    urls = sorted(set(re.findall(r"<loc>(https://www\.cebc4cw\.org/program/[^<]+)</loc>", xml)))
    print(f"CEBC: {len(urls)} program pages")

    records = []
    for i, url in enumerate(urls):
        html = fetch(url, delay=0.3)
        if not html:
            continue
        rec = parse_program(url, html)
        if rec:
            records.append(rec)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(urls)} ({len(records)} parsed)")

    save_source(
        "cebc",
        "California Evidence-Based Clearinghouse for Child Welfare (CEBC)",
        "https://www.cebc4cw.org/",
        records,
        notes=(
            "Programs relevant to child welfare, rated on the CEBC Scientific Rating "
            "Scale (1 = Well-Supported ... 5 = Concerning Practice; NR = Not able to "
            "be Rated)."
        ),
        rating_scale=RATING_LABELS,
    )


if __name__ == "__main__":
    main()
