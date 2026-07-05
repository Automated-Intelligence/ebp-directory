"""Scrape EffectiveChildTherapy.org (APA Division 53 / SCCAP).

Index page lists disorder/concern/symptom pages. Each page has one or more
tables where rows are evidence levels ("Level One: Works Well" ... "Level
Five: Tested and Does Not Work") and cells contain therapy names. Tables are
usually preceded by a <strong> age-group label like "Tested Therapies for
Young Children Under 8".
"""
import re
from html.parser import HTMLParser

from common import clean, fetch, save_source, strip_tags


class CellParser(HTMLParser):
    """Extract list items from a table cell, flattening nested lists as
    'Parent – Child' (e.g. 'CBT – Group'). A parent with children is not
    emitted on its own."""

    def __init__(self):
        super().__init__()
        self.buffers = []
        self.has_children = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.buffers.append("")
            self.has_children.append(False)

    def handle_endtag(self, tag):
        if tag == "li" and self.buffers:
            text = clean(self.buffers.pop())
            had_children = self.has_children.pop()
            if self.buffers:  # nested item -> prefix with parent text
                self.has_children[-1] = True
                parent = clean(self.buffers[-1])
                if parent and text:
                    text = f"{parent} – {text}"
            if text and not had_children:
                self.items.append(text)

    def handle_data(self, data):
        if self.buffers:
            self.buffers[-1] += data


def cell_items(cell_html):
    p = CellParser()
    p.feed(cell_html)
    return p.items if p.items else [strip_tags(cell_html)]

BASE = "https://effectivechildtherapy.org"
INDEX = BASE + "/concerns-symptoms-disorders/"

LEVELS = {
    "one": ("1", "Works Well"),
    "two": ("2", "Works"),
    "three": ("3", "Might Work"),
    "four": ("4", "Experimental"),
    "five": ("5", "Tested and Does Not Work"),
}


def acronym_map(html):
    """Pages define acronyms in prose, e.g. 'Behavioral classroom management
    (BCM)'; table cells then use the bare acronym."""
    text = strip_tags(html)
    out = {}
    for m in re.finditer(r"([A-Z][a-z][A-Za-z' -]{3,60}?)\s*\(([A-Z]{2,6})\)", text):
        out[m.group(2)] = f"{m.group(1).strip()} ({m.group(2)})"
    return out


def parse_page(url, html, records):
    title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    problem = strip_tags(title_m.group(1)) if title_m else url.rstrip("/").split("/")[-1]
    acronyms = acronym_map(html)

    # Track the age-group label that precedes each table.
    pieces = re.split(r"(<table.*?</table>)", html, flags=re.S)
    age_group = ""
    for piece in pieces:
        if not piece.startswith("<table"):
            labels = re.findall(r"<(?:strong|h[2-4])[^>]*>([^<]*[Tt]herapies[^<]*)</", piece)
            if labels:
                age_group = strip_tags(labels[-1])
                age_group = re.sub(r"^Tested Therapies for\s*", "", age_group, flags=re.I)
            continue
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", piece, re.S):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
            if len(cells) < 2:
                continue
            level_txt = strip_tags(cells[0]).lower()
            lm = re.search(r"level\s+(one|two|three|four|five)", level_txt)
            if not lm:
                continue
            level, label = LEVELS[lm.group(1)]
            for name in cell_items(cells[1]):
                name = clean(name)
                if not name or name.lower() in ("none", "n/a"):
                    continue
                if re.fullmatch(r"[A-Z]{2,6}", name) and name in acronyms:
                    name = acronyms[name]
                records.append(
                    {
                        "name": clean(name),
                        "problem": clean(problem),
                        "ageGroup": clean(age_group),
                        "level": level,
                        "levelLabel": label,
                        "url": url,
                    }
                )


def main():
    index = fetch(INDEX)
    if not index:
        raise SystemExit("could not fetch ECT index")
    urls = sorted(
        set(
            re.findall(
                r'href="(https://effectivechildtherapy\.org/concerns-symptoms-disorders/'
                r'(?:disorders|concerns|symptoms)/[a-z0-9-]+/)"',
                index,
            )
        )
    )
    urls = [u for u in urls if "landing-page" not in u]
    print(f"ECT: {len(urls)} topic pages")

    records = []
    for url in urls:
        html = fetch(url)
        if html:
            parse_page(url, html, records)

    save_source(
        "ect",
        "Effective Child Therapy (APA Division 53 / SCCAP)",
        INDEX,
        records,
        notes=(
            "Evidence-based treatments for children and adolescents, rated per "
            "disorder/concern using SCCAP's five-level system."
        ),
        rating_scale={
            "1": "Works Well (well-established)",
            "2": "Works (probably efficacious)",
            "3": "Might Work (possibly efficacious)",
            "4": "Experimental (untested or insufficient evidence)",
            "5": "Tested and Does Not Work",
        },
    )


if __name__ == "__main__":
    main()
