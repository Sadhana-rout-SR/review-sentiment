import csv
import os
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data_cleaning import deduplicate_reviews, extract_common_keywords
from sentiment_model import SentimentModel
from dashboard.charts import sentiment_chart_data, keyword_chart_data


load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "dataset", "reviews.csv")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
model = SentimentModel()


def fetch_google_reviews(query: str, max_reviews: int):
    """Fetch Google reviews using Places Text Search + Place Details endpoints."""
    if not GOOGLE_PLACES_API_KEY:
        return [], "google_api_key_missing"

    try:
        text_search_resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": GOOGLE_PLACES_API_KEY},
            timeout=12,
        )
        text_search_data = text_search_resp.json() if text_search_resp.ok else {}
        results = text_search_data.get("results", [])
        if not results:
            return [], "google_place_not_found"

        place_id = results[0].get("place_id", "")
        if not place_id:
            return [], "google_place_id_missing"

        details_resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={
                "place_id": place_id,
                "fields": "name,reviews,url",
                "reviews_sort": "newest",
                "key": GOOGLE_PLACES_API_KEY,
            },
            timeout=12,
        )

        details_data = details_resp.json() if details_resp.ok else {}
        raw_reviews = details_data.get("result", {}).get("reviews", [])

        rows = []
        for item in raw_reviews[:max_reviews]:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "platform": "google",
                    "author": item.get("author_name", ""),
                    "rating": item.get("rating", ""),
                    "published_at": item.get("relative_time_description", ""),
                    "text": text,
                    "source_url": details_data.get("result", {}).get("url", ""),
                }
            )

        return rows, "ok"
    except Exception:
        return [], "google_fetch_error"


def fetch_reddit_reviews(query: str, max_reviews: int):
    """Fetch social reviews from Reddit public search."""
    try:
        resp = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": f"{query} review", "sort": "new", "limit": min(max_reviews, 100)},
            headers={"User-Agent": "review-sentiment-ai/1.0"},
            timeout=12,
        )
        if not resp.ok:
            return [], "reddit_fetch_failed"

        data = resp.json()
        children = data.get("data", {}).get("children", [])
        rows = []

        for child in children:
            post = child.get("data", {})
            title = (post.get("title") or "").strip()
            body = (post.get("selftext") or "").strip()
            text = f"{title}. {body}".strip(". ")
            if len(text) < 20:
                continue

            created = post.get("created_utc")
            published_at = ""
            if created:
                published_at = datetime.fromtimestamp(float(created), tz=timezone.utc).isoformat()

            rows.append(
                {
                    "platform": "reddit",
                    "author": post.get("author", ""),
                    "rating": "",
                    "published_at": published_at,
                    "text": text,
                    "source_url": f"https://www.reddit.com{post.get('permalink', '')}",
                }
            )

            if len(rows) >= max_reviews:
                break

        return rows, "ok"
    except Exception:
        return [], "reddit_fetch_error"


def fetch_csv_reviews(max_reviews: int):
    """Load review rows from local dataset CSV file."""
    if not os.path.exists(DATASET_PATH):
        return [], "dataset_not_found"

    rows = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            text = (raw.get("review_text") or raw.get("text") or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "platform": raw.get("platform", "dataset"),
                    "author": raw.get("author", ""),
                    "rating": raw.get("rating", ""),
                    "published_at": raw.get("published_at", ""),
                    "text": text,
                    "source_url": raw.get("source_url", ""),
                }
            )
            if len(rows) >= max_reviews:
                break

    return rows, "ok"


def reviews_from_manual_input(manual_text: str, max_reviews: int):
    """Split multiline manual input into review rows."""
    lines = [line.strip() for line in (manual_text or "").splitlines() if line.strip()]
    rows = [
        {
            "platform": "manual",
            "author": "",
            "rating": "",
            "published_at": "",
            "text": line,
            "source_url": "",
        }
        for line in lines[:max_reviews]
    ]
    return rows, "ok" if rows else "manual_input_empty"


def compute_overall_satisfaction(positive_pct: float, negative_pct: float, avg_compound: float):
    """Convert sentiment signals to an easy-to-read customer satisfaction label."""
    normalized_compound = (avg_compound + 1) / 2 * 100
    net_sentiment = positive_pct - negative_pct
    score = round((0.6 * normalized_compound) + (0.4 * (net_sentiment + 100) / 2), 2)

    if score >= 80:
        label = "Very Satisfied"
    elif score >= 65:
        label = "Satisfied"
    elif score >= 45:
        label = "Neutral"
    elif score >= 30:
        label = "Dissatisfied"
    else:
        label = "Very Dissatisfied"

    return label, score


def build_analytics(analyzed_reviews):
    total = len(analyzed_reviews)
    if total == 0:
        return {
            "total_reviews": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "positive_percentage": 0.0,
            "negative_percentage": 0.0,
            "neutral_percentage": 0.0,
            "most_common_keywords": [],
            "overall_customer_satisfaction": "No data",
            "satisfaction_score": 0.0,
            "average_compound_score": 0.0,
        }

    positive_count = sum(1 for r in analyzed_reviews if r["sentiment"] == "Positive")
    negative_count = sum(1 for r in analyzed_reviews if r["sentiment"] == "Negative")
    neutral_count = total - positive_count - negative_count

    positive_pct = round((positive_count / total) * 100, 2)
    negative_pct = round((negative_count / total) * 100, 2)
    neutral_pct = round((neutral_count / total) * 100, 2)

    average_compound = round(sum(r.get("compound", 0.0) for r in analyzed_reviews) / total, 4)
    keywords = extract_common_keywords([r.get("text", "") for r in analyzed_reviews], limit=10)
    satisfaction_label, satisfaction_score = compute_overall_satisfaction(
        positive_pct, negative_pct, average_compound
    )

    return {
        "total_reviews": total,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "positive_percentage": positive_pct,
        "negative_percentage": negative_pct,
        "neutral_percentage": neutral_pct,
        "most_common_keywords": keywords,
        "overall_customer_satisfaction": satisfaction_label,
        "satisfaction_score": satisfaction_score,
        "average_compound_score": average_compound,
    }


def collect_reviews(source: str, query: str, max_reviews: int, manual_text: str):
    source = (source or "google").lower()

    if source == "google":
        return fetch_google_reviews(query, max_reviews)
    if source == "reddit":
        return fetch_reddit_reviews(query, max_reviews)
    if source == "csv":
        return fetch_csv_reviews(max_reviews)
    if source == "manual":
        return reviews_from_manual_input(manual_text, max_reviews)

    return [], "invalid_source"


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/style.css")
def style_css():
    return send_from_directory(FRONTEND_DIR, "style.css")


@app.route("/script.js")
def script_js():
    return send_from_directory(FRONTEND_DIR, "script.js")


@app.route("/api/analyze", methods=["POST"])
def analyze_reviews():
    payload = request.get_json(silent=True) or {}
    source = payload.get("source", "google")
    query = (payload.get("query") or "").strip()
    manual_text = payload.get("manual_text", "")

    try:
        max_reviews = int(payload.get("max_reviews", 50))
    except Exception:
        max_reviews = 50
    max_reviews = max(1, min(max_reviews, 200))

    if source in {"google", "reddit"} and not query:
        return jsonify({"error": "query is required for google/reddit sources"}), 400

    rows, source_status = collect_reviews(source, query, max_reviews, manual_text)
    rows = deduplicate_reviews(rows)

    if not rows:
        return jsonify(
            {
                "error": "No reviews found for this request",
                "source": source,
                "source_status": source_status,
            }
        ), 404

    analyzed = model.analyze_reviews(rows)
    analytics = build_analytics(analyzed)

    response = {
        "source": source,
        "source_status": source_status,
        "reviews": analyzed,
        "analytics": analytics,
        "charts": {
            "sentiment": sentiment_chart_data(analytics),
            "keywords": keyword_chart_data(analytics),
        },
    }
    return jsonify(response)


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "google_places_api_configured": bool(GOOGLE_PLACES_API_KEY),
            "dataset_file": DATASET_PATH,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
