"""
Chunking: split the tax law into pieces that are each small enough to match
a question precisely, but never cut a rule away from what it depends on.

Three ideas:

1. Split along the law's own structure. A section is the natural unit. A
   long section splits at its sub-sections "(1)", "(2)", ...; a Schedule at
   its numbered paragraphs. Neighbouring small pieces are merged back
   together, so no chunk is a lonely one-line fragment.

2. A piece that is still too long is cut between lines, never mid-line, and
   each continuation repeats the lead-in line it hangs off. "(b) Rs. 30000
   in any other case" means nothing without "the deduction shall not
   exceed—" above it.

3. Every chunk carries a header naming the Act, the section, the OLD 1961
   section number, the title and the tax year. The header is part of the
   text that gets embedded, so a question about "24(b)" can find section 22
   even though the law's own text never says "24".
"""

import json
import os
import re

CORPUS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus", "income_tax_act_2025.json")

MAX_WORDS = 350   # aim for chunks no longer than this
LEAD_WORDS = 40   # how much of a lead-in line to repeat on continuations

SUBSECTION = re.compile(r"^\(\d+[A-Z]?\)")         # "(1)", "(2A)"
SECTION_START = re.compile(r"^(\d+[A-Z]?\.|\(\d+\))")  # "22. (1) ...", "(101) ..."
NUMBERED_PARA = re.compile(r"^\d+\.\s")             # Schedule paragraphs "2. ..."


def load_corpus(path=CORPUS_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def words(text):
    return len(text.split())


def body_lines(section):
    """The section's lines, minus the chapter and title lines printed above it."""
    lines = section["text"].split("\n")
    if section["section"].startswith("Schedule"):
        return lines
    for i, line in enumerate(lines):
        if SECTION_START.match(line):
            return lines[i:]
    return lines


COLUMN_LETTERS = re.compile(r"([A-Z] )*[A-Z]")  # a table's "A B C" row


def is_heading(lines, i):
    """A short title line directly above a numbered paragraph, as in Schedules."""
    line = lines[i]
    return (
        i + 1 < len(lines)
        and NUMBERED_PARA.match(lines[i + 1]) is not None
        and not line.startswith("(")
        and not COLUMN_LETTERS.fullmatch(line)
        and words(line) <= 12
    )


def units(lines, schedule=False):
    """Group lines into the law's own units: sub-sections, or a Schedule's titled paragraphs.

    Titles only count in Schedules; inside sections, short lines like a
    table's "A B C" row also sit above numbered lines and must not split.
    """
    def heading(i):
        return schedule and is_heading(lines, i)

    groups = []
    for i, line in enumerate(lines):
        starts_new = SUBSECTION.match(line) or heading(i)
        if starts_new and not (i > 0 and heading(i - 1)):
            groups.append([line])
        elif groups:
            groups[-1].append(line)
        else:
            groups.append([line])
    return groups


def split_long(unit, before=()):
    """Cut an over-long unit between lines; continuations repeat its lead-in.

    `before` is a short preamble kept in front of the first piece.
    """
    lead = unit[0]
    if len(unit) > 1 and NUMBERED_PARA.match(unit[1]) and not lead.startswith("("):
        lead = f"{lead} {unit[1]}"  # a Schedule title plus its opening line
    short_lead = " ".join(lead.split()[:LEAD_WORDS]) + (" …" if words(lead) > LEAD_WORDS else "")
    pieces, current = [], list(before)
    for line in unit:
        if current and words("\n".join(current + [line])) > MAX_WORDS:
            pieces.append(current)
            current = [f"[continued] {short_lead}"]
        current.append(line)
    pieces.append(current)
    return ["\n".join(p) for p in pieces]


def pack(groups):
    """Merge neighbouring units while they fit; split any that are too big alone."""
    chunks, current = [], ""
    for group in groups:
        text = "\n".join(group)
        if words(text) > MAX_WORDS:
            before = ()
            if current and words(current) < 60:
                before = current.split("\n")  # don't strand a short preamble
            elif current:
                chunks.append(current)
            current = ""
            chunks.extend(split_long(group, before))
        elif current and words(current) + words(text) > MAX_WORDS:
            chunks.append(current)
            current = text
        else:
            current = f"{current}\n{text}" if current else text
    if current:
        chunks.append(current)
    return chunks


def header(corpus, section):
    s = section["section"]
    name = s if s.startswith("Schedule") else f"section {s}"
    return (
        f"Income-tax Act, 2025, {name} (old Income-tax Act, 1961: section {section['old_section']}). "
        f"{section['title']}. Tax year {corpus['tax_year']}."
    )


def build_chunks(corpus):
    chunks = []
    for section in corpus["sections"]:
        head = header(corpus, section)
        pieces = pack(units(body_lines(section), schedule=section["section"].startswith("Schedule")))
        for n, text in enumerate(pieces, start=1):
            chunks.append({
                "id": f"{section['section']}#{n}",
                "section": section["section"],
                "old_section": section["old_section"],
                "title": section["title"],
                "part": n,
                "parts": len(pieces),
                "source_url": section["source_url"],
                "text": text,
                "embed_text": f"{head}\n{text}",
            })
    return chunks


def fixed_size_chunks(corpus, size=200):
    """The naive way, for comparison: every `size` words, wherever that falls."""
    out = []
    for section in corpus["sections"]:
        tokens = section["text"].split()
        for start in range(0, len(tokens), size):
            out.append({"section": section["section"], "text": " ".join(tokens[start:start + size])})
    return out
