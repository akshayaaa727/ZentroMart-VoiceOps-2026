from pathlib import Path
import re

KB_DIR = Path(__file__).parent / "kb"

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "can", "could", "would", "should",
    "i", "me", "my", "you", "your", "we", "our", "it", "this",
    "that", "for", "to", "of", "in", "on", "at", "and", "or",
    "what", "how", "when", "where", "who", "which", "tell", "please"
}


def tokenize(text):
    words = re.findall(r"\b[a-z0-9]+\b", text.lower())
    return [word for word in words if word not in STOP_WORDS]


def load_documents():
    documents = []

    for path in sorted(KB_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")

        # Split before headings, preserving each heading with its section.
        sections = re.split(r"(?m)(?=^#{1,3}\s+)", content)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            match = re.match(r"^#{1,3}\s+(.+)", section)
            heading = match.group(1).strip() if match else path.stem

            documents.append({
                "source": path.name,
                "heading": heading,
                "text": section
            })

    return documents


def retrieve(query, documents, top_k=4):
    query_words = set(tokenize(query))
    results = []

    for doc in documents:
        text_words = set(tokenize(doc["text"]))
        heading_words = set(tokenize(doc["heading"]))

        score = len(query_words & text_words)
        score += 2 * len(query_words & heading_words)

        # Reward exact phrase matches.
        normalized_query = " ".join(tokenize(query))
        normalized_text = " ".join(tokenize(doc["text"]))

        if normalized_query and normalized_query in normalized_text:
            score += 4

        source = doc["source"].lower()

        # Prefer the current policy over older or general guidance.
        if "superseded" in source or "deprecated" in source:
            score -= 8
        elif source.startswith("pol_"):
            score += 1.5

        if source.startswith("faq"):
            score -= 0.5

        if score > 0:
            results.append({**doc, "score": score})

    return sorted(
        results,
        key=lambda item: item["score"],
        reverse=True
    )[:top_k]


if __name__ == "__main__":
    documents = load_documents()
    print(f"Loaded {len(documents)} knowledge-base sections.")

    tests = [
        "What is the return window for electronics?",
        "How long does a UPI refund take?",
        "What is the return policy for grocery items?",
        "How do I verify my identity?"
    ]

    for question in tests:
        print(f"\nQuestion: {question}")
        for result in retrieve(question, documents, top_k=3):
            print(
                f"- {result['source']} | {result['heading']} "
                f"| score={result['score']}"
            )
