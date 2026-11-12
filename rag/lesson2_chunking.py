"""
RAG lesson 2: chunking the real tax law
=======================================
Lesson 1 searched nine hand-written sentences. Real documents are long, so
they have to be cut into chunks before embedding: one vector per chunk.

How you cut decides what can be found:
  - too big:  one vector has to stand for many rules, so it matches none well
  - too small: a rule gets separated from its conditions and limits
  - wrong place: "shall not exceed—" ends up in one chunk, "Rs. 200000" in the next

This script compares three ways of chunking the same 35 sections of the
Income-tax Act, 2025 (rag/corpus/income_tax_act_2025.json):

  A. naive       every 200 words, wherever that falls, no labels
  B. structure   cut along sections and sub-sections (rag/chunking.py), no labels
  C. labelled    B, plus a header with the section, OLD section number and title

For 12 questions with a known right section, it reports where the first
chunk from the right section ranks. Rank 1 is perfect.

Run from the repo root:   python rag/lesson2_chunking.py
First run embeds about 320 chunks (cached in rag/.cache for later runs).
"""

import statistics
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chunking import MAX_WORDS, build_chunks, fixed_size_chunks, load_corpus  # noqa: E402
from embed import cosine, embed  # noqa: E402

# Each question with the section(s) that answer it.
QUESTIONS = [
    ("What does section 24(b) allow?", {"22"}),
    ("How much home loan interest can I deduct on a house I live in?", {"22"}),
    ("Is money put into ELSS eligible for the 1.5 lakh deduction?", {"123", "Schedule XV"}),
    ("What does 80C cover?", {"123", "Schedule XV"}),
    ("What is the tax rate on long-term gains from equity mutual funds?", {"198"}),
    ("How long must I hold equity fund units for the gain to be long-term?", {"2(101)"}),
    ("Under the new regime, is income up to 12 lakh tax-free because of the rebate?", {"156"}),
    ("What are the slab rates in the new tax regime?", {"202"}),
    ("Are gains on debt mutual funds bought after April 2023 always short-term?", {"76"}),
    ("Can I claim a deduction for interest on my savings account?", {"153"}),
    ("What is the deduction limit for health insurance premium paid for my parents?", {"126"}),
    ("Can a capital loss be set off against my salary?", {"109"}),
]


def rank_of_right_section(question_vector, chunks, vectors, right):
    """1-based position of the first chunk from a right section."""
    order = sorted(range(len(chunks)), key=lambda i: cosine(question_vector, vectors[i]), reverse=True)
    for position, i in enumerate(order, start=1):
        if chunks[i]["section"] in right:
            return position
    return None


def show_naive_cut(corpus):
    """Where 200-word chunking cuts section 22, the home-loan interest rule."""
    section = next(s for s in corpus["sections"] if s["section"] == "22")
    tokens = section["text"].split()
    print("Naive chunking cuts section 22 at word 200. The end of chunk 1:")
    print("   ..." + " ".join(tokens[175:200]))
    print("and the start of chunk 2:")
    print("   " + " ".join(tokens[200:225]) + " ...\n")


def main():
    corpus = load_corpus()
    labelled = build_chunks(corpus)
    naive = fixed_size_chunks(corpus, size=200)

    sizes = [len(c["text"].split()) for c in labelled]
    split_sections = len({c["section"] for c in labelled if c["parts"] > 1})
    print(f"{len(corpus['sections'])} sections -> {len(labelled)} structure-aware chunks "
          f"(limit {MAX_WORDS} words; {split_sections} sections needed splitting)")
    print(f"chunk size in words: min {min(sizes)}, median {statistics.median(sizes):.0f}, max {max(sizes)}")
    print(f"naive 200-word chunking gives {len(naive)} chunks\n")

    show_naive_cut(corpus)

    example = next(c for c in labelled if c["id"] == "22#1")
    print("The labelled chunk that holds the same rule starts:")
    print("   " + example["embed_text"][:300].replace("\n", "\n   ") + " ...\n")

    variants = {
        "A naive": (naive, embed([c["text"] for c in naive], "RETRIEVAL_DOCUMENT")),
        "B structure": (labelled, embed([c["text"] for c in labelled], "RETRIEVAL_DOCUMENT")),
        "C labelled": (labelled, embed([c["embed_text"] for c in labelled], "RETRIEVAL_DOCUMENT")),
    }
    question_vectors = embed([q for q, _ in QUESTIONS], "RETRIEVAL_QUERY")

    print(f"{'Question':<78} {'A':>4} {'B':>4} {'C':>4}")
    ranks = {name: [] for name in variants}
    for (question, right), qv in zip(QUESTIONS, question_vectors):
        row = []
        for name, (chunks, vectors) in variants.items():
            r = rank_of_right_section(qv, chunks, vectors, right)
            ranks[name].append(r)
            row.append(f"{r:>4}")
        print(f"{question[:77]:<78} {' '.join(row)}")

    print("\nRight section ranked first / in the top 3 / in the top 5:")
    for name, rs in ranks.items():
        n = len(rs)
        top1 = sum(r == 1 for r in rs)
        top3 = sum(r <= 3 for r in rs)
        top5 = sum(r <= 5 for r in rs)
        print(f"  {name:<12} {top1:>2}/{n}   {top3:>2}/{n}   {top5:>2}/{n}")


if __name__ == "__main__":
    main()
