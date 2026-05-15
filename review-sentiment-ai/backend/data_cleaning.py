import re
from collections import Counter

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for", "from",
    "had", "has", "have", "he", "her", "him", "his", "i", "if", "in", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "she", "so", "that", "the", "their",
    "them", "there", "they", "this", "to", "us", "was", "we", "were", "with", "you", "your"
}


def clean_review_text(text: str) -> str:
    """Normalize whitespace and strip noisy characters while preserving readable text."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^A-Za-z0-9\s'.,!?-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_valid_review(text: str, min_words: int = 4) -> bool:
    """Basic validation to reject empty or very short text snippets."""
    cleaned = clean_review_text(text)
    if not cleaned:
        return False
    return len(cleaned.split()) >= min_words


def deduplicate_reviews(review_rows):
    """Remove duplicate reviews by case-insensitive text."""
    deduped = []
    seen = set()

    for row in review_rows:
        text = clean_review_text(row.get("text", ""))
        if not is_valid_review(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(row)
        normalized["text"] = text
        deduped.append(normalized)

    return deduped


def extract_common_keywords(texts, limit: int = 10):
    """Extract most common non-stopword tokens from review text."""
    counter = Counter()

    for text in texts:
        cleaned = clean_review_text(text).lower()
        tokens = re.findall(r"[a-zA-Z']+", cleaned)
        filtered = [t for t in tokens if len(t) > 2 and t not in STOPWORDS]
        counter.update(filtered)

    return [{"keyword": word, "count": count} for word, count in counter.most_common(limit)]
