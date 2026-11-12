"""
RAG lesson 1: embeddings and cosine similarity
==============================================
An embedding model turns a piece of text into a list of numbers (a vector).
It is trained so that texts with similar MEANING get vectors pointing in
similar directions, even when they share no words. Retrieval in RAG is just:
embed the question, then find the stored passages whose vectors point the
closest way.

"Closest" is measured with cosine similarity: the cosine of the angle
between two vectors.
     1.0  -> same direction (same meaning)
     0.0  -> unrelated
    In practice related texts score around 0.6-0.8 and unrelated ones lower.
    The absolute numbers matter less than the ORDER.

This script:
  1. embeds a few short tax sentences (the "documents")
  2. embeds a few questions
  3. ranks the sentences for each question two ways:
       - by cosine similarity (meaning)
       - by shared words (keyword search, for contrast)

Run from the repo root:   python rag/lesson1_embeddings.py
Needs GEMINI_API_KEY in .env. Uses about 15 embedding calls' worth of quota.
"""

import math
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(".env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-embedding-2"
# The model's full vectors have 3072 numbers. It is trained so the first N
# numbers still work on their own ("Matryoshka" embeddings), so we keep 768:
# a quarter of the storage, for a small loss in quality.
DIMENSIONS = 768


def embed(texts, task_type):
    """One vector per text.

    task_type tells the model what the text is for:
      RETRIEVAL_DOCUMENT  a passage that will be searched
      RETRIEVAL_QUERY     a question doing the searching
    Questions and passages are worded differently ("can I...?" vs "a person
    may..."), and the model was trained to bridge that gap.

    Each text goes in its own Content. Passing a plain list of strings to
    this model merges them into ONE embedding, which is not what we want.
    """
    response = client.models.embed_content(
        model=MODEL,
        contents=[types.Content(parts=[types.Part(text=t)]) for t in texts],
        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIMENSIONS),
    )
    return [e.values for e in response.embeddings]


def cosine(a, b):
    """cos(angle) = (a . b) / (|a| * |b|), written out by hand.

    a . b  multiplies the vectors number by number and adds it all up.
    |a|    is the vector's length, sqrt(a . a).
    Dividing by the lengths means only the DIRECTION counts, not the size.
    """
    dot = sum(x * y for x, y in zip(a, b))
    length_a = math.sqrt(sum(x * x for x in a))
    length_b = math.sqrt(sum(y * y for y in b))
    return dot / (length_a * length_b)


STOP_WORDS = {"a", "an", "the", "of", "on", "in", "to", "is", "are", "be", "can", "i",
              "my", "if", "for", "what", "how", "much", "does", "do", "and", "at", "up",
              "from", "by", "it", "you", "your", "will", "under", "any", "within"}


def words(text):
    return {w for w in re.findall(r"[a-z0-9()]+", text.lower()) if w not in STOP_WORDS}


def shared_words(question, sentence):
    """The crudest keyword search: how many meaningful words appear in both."""
    return len(words(question) & words(sentence))


# Short paraphrases, NOT the law's wording. Lesson 2 swaps these for the real
# text of the Act. Number 9 is off-topic on purpose: it should always rank last.
SENTENCES = [
    "Long-term capital gains on equity mutual funds are tax-free up to Rs 1.25 lakh in a financial year.",
    "Long-term gains on equity funds above that limit are taxed at 12.5%.",
    "Equity fund units sold within 12 months of buying give short-term gains, taxed at 20%.",
    "Under the old regime, interest paid on a loan for a self-occupied house can be deducted up to Rs 2 lakh a year.",
    "Under the old regime, PF contributions, ELSS investments and life insurance premiums can be deducted up to Rs 1.5 lakh a year.",
    "In the new regime, a resident whose taxable income is up to Rs 12 lakh pays no tax because of a rebate.",
    "Interest earned on a savings bank account is added to your income and taxed at your slab rate.",
    "Some mutual funds charge an exit load if you redeem units within a year of buying them.",
    "India won the cricket match by six wickets.",
]

# Each question with the sentence number a good search should put first.
QUESTIONS = [
    ("Can I reduce my tax on what I pay the bank for my house?", 4),
    ("How much profit from selling my mutual funds is free of tax?", 1),
    ("I earn 11 lakh. Will I owe anything under the new system?", 6),
    ("Is there a penalty for withdrawing from a fund early?", 8),
    ("What does section 24(b) allow?", 4),
]


def main():
    sentence_vectors = embed(SENTENCES, "RETRIEVAL_DOCUMENT")
    question_vectors = embed([q for q, _ in QUESTIONS], "RETRIEVAL_QUERY")

    v = sentence_vectors[0]
    print(f"Each embedding is a list of {len(v)} numbers. The first six of sentence 1:")
    print("  " + ", ".join(f"{x:+.4f}" for x in v[:6]) + ", ...")
    print("On their own they mean nothing; only comparing two vectors does.\n")

    meaning_hits = keyword_hits = 0
    for (question, expected), qv in zip(QUESTIONS, question_vectors):
        by_meaning = sorted(
            ((cosine(qv, sv), i + 1) for i, sv in enumerate(sentence_vectors)), reverse=True
        )
        # Ties in shared words go to the earlier sentence, as a naive search would.
        by_keyword = sorted(
            ((shared_words(question, s), -(i + 1)) for i, s in enumerate(SENTENCES)), reverse=True
        )
        top_meaning = by_meaning[0][1]
        top_keyword = -by_keyword[0][1]
        meaning_hits += top_meaning == expected
        keyword_hits += top_keyword == expected

        print(f"Q: {question}")
        print(f"   expected sentence {expected}")
        for score, n in by_meaning[:3]:
            mark = "  <- expected" if n == expected else ""
            print(f"   {score:.3f}  #{n}  {SENTENCES[n - 1][:70]}{mark}")
        print(f"   lowest: {by_meaning[-1][0]:.3f}  #{by_meaning[-1][1]}")
        print(f"   keyword search's top pick: #{top_keyword} ({by_keyword[0][0]} shared words)\n")

    print(f"Right sentence ranked first: meaning {meaning_hits}/{len(QUESTIONS)}, "
          f"keywords {keyword_hits}/{len(QUESTIONS)}")


if __name__ == "__main__":
    main()
