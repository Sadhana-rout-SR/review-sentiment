import os
import sys
from datetime import datetime
from datetime import timedelta
import re

import pandas as pd
import plotly.express as px
import streamlit as st
from wordcloud import WordCloud
import matplotlib.pyplot as plt

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.sentiment_model import SentimentModel
from backend.data_cleaning import clean_review_text, extract_common_keywords

DATASET_PATH = os.path.join(PROJECT_ROOT, "dataset", "reviews.csv")
EXPORT_DIR = os.path.join(PROJECT_ROOT, "dataset", "bi_exports")


def _normalize_datetime_series(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    return parsed.dt.tz_convert(None)


def _parse_relative_time_to_datetime(value: str):
    """Parse values like '2 days ago' into approximate UTC datetimes."""
    if not isinstance(value, str):
        return None

    text = value.strip().lower()
    if not text:
        return None
    if text in {"today", "just now", "now"}:
        return datetime.utcnow()
    if text == "yesterday":
        return datetime.utcnow() - timedelta(days=1)

    match = re.search(r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago", text)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    if "minute" in unit:
        return datetime.utcnow() - timedelta(minutes=amount)
    if "hour" in unit:
        return datetime.utcnow() - timedelta(hours=amount)
    if "day" in unit:
        return datetime.utcnow() - timedelta(days=amount)
    if "week" in unit:
        return datetime.utcnow() - timedelta(weeks=amount)
    if "month" in unit:
        return datetime.utcnow() - timedelta(days=30 * amount)
    if "year" in unit:
        return datetime.utcnow() - timedelta(days=365 * amount)
    return None


def _find_and_parse_date_column(df: pd.DataFrame) -> pd.Series:
    """Find a likely date column and parse multiple formats robustly."""
    candidate_cols = ["published_at", "publishedAt", "date", "created_at", "createdAt", "timestamp", "time"]

    for col in candidate_cols:
        if col not in df.columns:
            continue

        raw = df[col]
        primary = _normalize_datetime_series(raw)
        primary_ratio = primary.notna().mean() if len(primary) else 0

        fallback = pd.Series(raw.astype(str).map(_parse_relative_time_to_datetime), index=df.index)
        fallback = _normalize_datetime_series(fallback)
        merged = primary.fillna(fallback)
        merged_ratio = merged.notna().mean() if len(merged) else 0

        if merged_ratio > 0:
            return merged

    return pd.Series([pd.NaT] * len(df), index=df.index)


def load_reviews(csv_path: str):
    if not os.path.exists(csv_path):
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    if "review_text" in df.columns and "text" not in df.columns:
        df["text"] = df["review_text"]
    if "published_at" not in df.columns:
        df["published_at"] = ""

    df["text"] = df["text"].fillna("").astype(str).map(clean_review_text)
    df = df[df["text"].str.len() > 0].copy()

    df["parsed_date"] = _find_and_parse_date_column(df)
    return df


def apply_sentiment(df: pd.DataFrame):
    model = SentimentModel()
    sentiments = df["text"].map(model.classify)
    sent_df = pd.json_normalize(sentiments)
    out = pd.concat([df.reset_index(drop=True), sent_df], axis=1)
    return out


def sentiment_pie(df: pd.DataFrame):
    counts = df["sentiment"].value_counts().reset_index()
    counts.columns = ["Sentiment", "Count"]
    fig = px.pie(
        counts,
        names="Sentiment",
        values="Count",
        color="Sentiment",
        color_discrete_map={"Positive": "#16a34a", "Negative": "#dc2626", "Neutral": "#f59e0b"},
        title="Sentiment Distribution",
    )
    fig.update_layout(legend_title=None)
    return fig


def monthly_trend(df: pd.DataFrame):
    dated = df.dropna(subset=["parsed_date"]).copy()
    if dated.empty:
        return None

    dated["Month"] = dated["parsed_date"].dt.to_period("M").astype(str)
    monthly = (
        dated.groupby(["Month", "sentiment"]).size().reset_index(name="Count")
        .sort_values("Month")
    )

    fig = px.line(
        monthly,
        x="Month",
        y="Count",
        color="sentiment",
        markers=True,
        color_discrete_map={"Positive": "#16a34a", "Negative": "#dc2626", "Neutral": "#f59e0b"},
        title="Monthly Sentiment Trend",
    )
    fig.update_layout(xaxis_title="Month", yaxis_title="Review Count", legend_title=None)
    return fig


def daily_performance(df: pd.DataFrame):
    dated = df.dropna(subset=["parsed_date"]).copy()
    if dated.empty:
        return None, None

    dated["Day"] = dated["parsed_date"].dt.date
    daily_counts = dated.groupby("Day").size().reset_index(name="Reviews")
    daily_counts["Day"] = pd.to_datetime(daily_counts["Day"])
    daily_counts = daily_counts.sort_values("Day")

    fig = px.bar(
        daily_counts,
        x="Day",
        y="Reviews",
        title="Daily Review Performance",
        color_discrete_sequence=["#2563eb"],
    )
    fig.update_layout(xaxis_title="Date", yaxis_title="Review Count", showlegend=False)

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    by_day = {d.date(): int(v) for d, v in zip(daily_counts["Day"], daily_counts["Reviews"])}
    today_reviews = by_day.get(today, 0)
    yesterday_reviews = by_day.get(yesterday, 0)
    avg_daily = round(float(daily_counts["Reviews"].mean()), 2) if not daily_counts.empty else 0.0

    if yesterday_reviews > 0:
        growth_pct = round(((today_reviews - yesterday_reviews) / yesterday_reviews) * 100, 2)
    elif today_reviews > 0:
        growth_pct = 100.0
    else:
        growth_pct = 0.0

    summary = {
        "today_reviews": today_reviews,
        "yesterday_reviews": yesterday_reviews,
        "avg_daily_reviews": avg_daily,
        "growth_pct": growth_pct,
    }
    return fig, summary


def keyword_cloud(df: pd.DataFrame):
    text_blob = " ".join(df["text"].tolist()).strip()
    if not text_blob:
        return None

    wc = WordCloud(
        width=1100,
        height=420,
        background_color="white",
        collocations=False,
        colormap="viridis",
    ).generate(text_blob)

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    return fig


def top_reviews(df: pd.DataFrame, n: int = 5):
    top_pos = df.sort_values("compound", ascending=False).head(n)
    top_neg = df.sort_values("compound", ascending=True).head(n)
    return top_pos, top_neg


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def create_bi_exports(analyzed: pd.DataFrame, keywords_df: pd.DataFrame):
    """Create Power BI/Tableau-ready exports and return in-memory files for download."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    reviews_export = analyzed[[
        "platform", "author", "rating", "published_at", "text", "sentiment", "compound",
        "positive_score", "negative_score", "neutral_score",
    ]].copy()
    reviews_export = reviews_export.rename(columns={"text": "review_text"})
    reviews_export["month"] = pd.to_datetime(reviews_export["published_at"], errors="coerce").dt.to_period("M").astype(str)

    monthly_export = (
        reviews_export.groupby(["month", "sentiment"]).size().reset_index(name="review_count")
        .sort_values(["month", "sentiment"])
    )

    if "parsed_date" in analyzed.columns:
        daily_export = analyzed.dropna(subset=["parsed_date"]).copy()
        daily_export["date"] = pd.to_datetime(daily_export["parsed_date"]).dt.date.astype(str)
        daily_export = (
            daily_export.groupby(["date", "sentiment"]).size().reset_index(name="review_count")
            .sort_values(["date", "sentiment"])
        )
    else:
        daily_export = pd.DataFrame(columns=["date", "sentiment", "review_count"])

    sentiment_summary_export = pd.DataFrame([
        {
            "total_reviews": int(len(reviews_export)),
            "positive_reviews": int((reviews_export["sentiment"] == "Positive").sum()),
            "negative_reviews": int((reviews_export["sentiment"] == "Negative").sum()),
            "neutral_reviews": int((reviews_export["sentiment"] == "Neutral").sum()),
            "positive_percentage": round((reviews_export["sentiment"] == "Positive").mean() * 100, 2),
            "negative_percentage": round((reviews_export["sentiment"] == "Negative").mean() * 100, 2),
            "neutral_percentage": round((reviews_export["sentiment"] == "Neutral").mean() * 100, 2),
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        }
    ])

    os.makedirs(EXPORT_DIR, exist_ok=True)
    files = {
        f"bi_reviews_detail_{timestamp}.csv": _to_csv_bytes(reviews_export),
        f"bi_monthly_sentiment_{timestamp}.csv": _to_csv_bytes(monthly_export),
        f"bi_daily_sentiment_{timestamp}.csv": _to_csv_bytes(daily_export),
        f"bi_keyword_frequency_{timestamp}.csv": _to_csv_bytes(keywords_df),
        f"bi_sentiment_summary_{timestamp}.csv": _to_csv_bytes(sentiment_summary_export),
    }

    for filename, content in files.items():
        with open(os.path.join(EXPORT_DIR, filename), "wb") as f:
            f.write(content)

    return files


def main():
    st.set_page_config(page_title="Review Sentiment Dashboard", layout="wide")
    st.title("Customer Review Sentiment Dashboard")
    st.caption("Tools used: Streamlit + Plotly (with keyword cloud and ranked review insights)")

    csv_path = st.text_input("Dataset CSV path", value=DATASET_PATH)
    review_limit = st.slider("Max reviews to analyze", min_value=10, max_value=5000, value=1000, step=10)

    df = load_reviews(csv_path)
    if df.empty:
        st.error("No reviews found. Check CSV path and columns like review_text or text.")
        return

    df = df.head(review_limit)
    analyzed = apply_sentiment(df)

    total_reviews = len(analyzed)
    pos_pct = (analyzed["sentiment"].eq("Positive").mean() * 100).round(2)
    neg_pct = (analyzed["sentiment"].eq("Negative").mean() * 100).round(2)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Reviews", total_reviews)
    c2.metric("Positive %", f"{pos_pct}%")
    c3.metric("Negative %", f"{neg_pct}%")

    st.plotly_chart(sentiment_pie(analyzed), use_container_width=True)

    st.subheader("Daily Review Performance")
    daily_fig, daily_summary = daily_performance(analyzed)
    if daily_fig is not None:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Today Reviews", daily_summary["today_reviews"])
        d2.metric("Yesterday Reviews", daily_summary["yesterday_reviews"])
        d3.metric("Avg Reviews / Day", daily_summary["avg_daily_reviews"])
        d4.metric("Daily Growth %", f"{daily_summary['growth_pct']}%")
        st.plotly_chart(daily_fig, use_container_width=True)
    else:
        st.info("Daily performance needs valid date fields like published_at/date/created_at.")

    trend_fig = monthly_trend(analyzed)
    if trend_fig is not None:
        st.plotly_chart(trend_fig, use_container_width=True)
    else:
        st.info("Monthly trend graph needs valid date fields like published_at/date/created_at.")

    st.subheader("Keyword Cloud")
    wc_fig = keyword_cloud(analyzed)
    if wc_fig is not None:
        st.pyplot(wc_fig, clear_figure=True)
    else:
        st.info("Not enough text to build keyword cloud.")

    st.subheader("Most Common Keywords")
    keywords = extract_common_keywords(analyzed["text"].tolist(), limit=15)
    kw_df = pd.DataFrame(keywords)
    st.dataframe(kw_df, use_container_width=True)

    st.subheader("Power BI / Tableau Export")
    st.caption("One-click export creates BI-ready CSV files in dataset/bi_exports and provides direct downloads.")
    if st.button("Generate BI Export Files", type="primary"):
        exported = create_bi_exports(analyzed, kw_df)
        st.session_state["bi_exports"] = exported
        st.success(f"Export complete. {len(exported)} files created in dataset/bi_exports.")

    if "bi_exports" in st.session_state:
        for filename, content in st.session_state["bi_exports"].items():
            st.download_button(
                label=f"Download {filename}",
                data=content,
                file_name=filename,
                mime="text/csv",
            )

    st.subheader("Top Positive / Negative Reviews")
    top_n = st.slider("How many top reviews", min_value=3, max_value=20, value=5)
    top_pos, top_neg = top_reviews(analyzed, n=top_n)

    left, right = st.columns(2)
    with left:
        st.markdown("### Top Positive Reviews")
        st.dataframe(
            top_pos[["text", "compound", "sentiment", "platform"]].rename(
                columns={"text": "Review", "compound": "Score", "platform": "Source"}
            ),
            use_container_width=True,
        )

    with right:
        st.markdown("### Top Negative Reviews")
        st.dataframe(
            top_neg[["text", "compound", "sentiment", "platform"]].rename(
                columns={"text": "Review", "compound": "Score", "platform": "Source"}
            ),
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
