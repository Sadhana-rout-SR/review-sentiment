import os
import sys
import io
import base64
from urllib.parse import quote
from datetime import datetime
from datetime import timedelta
import re

import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, dash_table
from wordcloud import WordCloud
import matplotlib.pyplot as plt

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.sentiment_model import SentimentModel
from backend.data_cleaning import clean_review_text

DATASET_PATH = os.path.join(PROJECT_ROOT, "dataset", "reviews.csv")
EXPORT_DIR = os.path.join(PROJECT_ROOT, "dataset", "bi_exports")


def _normalize_datetime_series(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    return parsed.dt.tz_convert(None)


def _parse_relative_time_to_datetime(value: str):
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
    candidate_cols = ["published_at", "publishedAt", "date", "created_at", "createdAt", "timestamp", "time"]
    for col in candidate_cols:
        if col not in df.columns:
            continue

        raw = df[col]
        primary = _normalize_datetime_series(raw)
        fallback = pd.Series(raw.astype(str).map(_parse_relative_time_to_datetime), index=df.index)
        fallback = _normalize_datetime_series(fallback)
        merged = primary.fillna(fallback)
        if merged.notna().any():
            return merged

    return pd.Series([pd.NaT] * len(df), index=df.index)


def load_data():
    if not os.path.exists(DATASET_PATH):
        return pd.DataFrame(columns=["text", "published_at", "platform"])

    df = pd.read_csv(DATASET_PATH)
    if "review_text" in df.columns and "text" not in df.columns:
        df["text"] = df["review_text"]
    if "published_at" not in df.columns:
        df["published_at"] = ""
    if "platform" not in df.columns:
        df["platform"] = "dataset"

    df["text"] = df["text"].fillna("").astype(str).map(clean_review_text)
    df = df[df["text"].str.len() > 0].copy()

    model = SentimentModel()
    sent_df = pd.json_normalize(df["text"].map(model.classify))
    df = pd.concat([df.reset_index(drop=True), sent_df], axis=1)
    df["parsed_date"] = _find_and_parse_date_column(df)
    return df


def keyword_cloud_image(df: pd.DataFrame):
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

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("utf-8")


def top_reviews(df: pd.DataFrame, n: int = 5):
    top_pos = df.sort_values("compound", ascending=False).head(n).copy()
    top_neg = df.sort_values("compound", ascending=True).head(n).copy()

    keep_cols = ["text", "compound", "sentiment", "platform"]
    top_pos = top_pos[keep_cols].rename(columns={"text": "Review", "compound": "Score", "platform": "Source"})
    top_neg = top_neg[keep_cols].rename(columns={"text": "Review", "compound": "Score", "platform": "Source"})
    top_pos["Score"] = top_pos["Score"].round(4)
    top_neg["Score"] = top_neg["Score"].round(4)
    return top_pos, top_neg


def build_bi_exports(df: pd.DataFrame):
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for col, default_value in {"author": "", "rating": None, "published_at": "", "platform": "dataset"}.items():
        if col not in df.columns:
            df[col] = default_value

    reviews_export = df[[
        "platform", "author", "rating", "published_at", "text", "sentiment", "compound",
        "positive_score", "negative_score", "neutral_score",
    ]].copy()
    reviews_export = reviews_export.rename(columns={"text": "review_text"})

    date_for_month = pd.to_datetime(reviews_export["published_at"], errors="coerce")
    if "parsed_date" in df.columns:
        date_for_month = date_for_month.fillna(pd.to_datetime(df["parsed_date"], errors="coerce"))
    reviews_export["month"] = date_for_month.dt.to_period("M").astype(str)

    monthly_export = (
        reviews_export.groupby(["month", "sentiment"]).size().reset_index(name="review_count")
        .sort_values(["month", "sentiment"])
    )

    daily_export = df.dropna(subset=["parsed_date"]).copy()
    if not daily_export.empty:
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
        f"bi_reviews_detail_{timestamp}.csv": reviews_export,
        f"bi_monthly_sentiment_{timestamp}.csv": monthly_export,
        f"bi_daily_sentiment_{timestamp}.csv": daily_export,
        f"bi_sentiment_summary_{timestamp}.csv": sentiment_summary_export,
    }

    downloads = {}
    for filename, export_df in files.items():
        csv_text = export_df.to_csv(index=False)
        with open(os.path.join(EXPORT_DIR, filename), "w", encoding="utf-8", newline="") as f:
            f.write(csv_text)
        downloads[filename] = "data:text/csv;charset=utf-8," + quote(csv_text)

    return downloads


def build_app():
    df = load_data()

    sentiment_counts = df["sentiment"].value_counts().reset_index()
    sentiment_counts.columns = ["Sentiment", "Count"]
    pie = px.pie(
        sentiment_counts,
        names="Sentiment",
        values="Count",
        title="Sentiment Pie Chart",
        color="Sentiment",
        color_discrete_map={"Positive": "#16a34a", "Negative": "#dc2626", "Neutral": "#f59e0b"},
    )

    trend_df = df.dropna(subset=["parsed_date"]).copy()
    if not trend_df.empty:
        trend_df["Month"] = trend_df["parsed_date"].dt.to_period("M").astype(str)
        trend_df = trend_df.groupby(["Month", "sentiment"]).size().reset_index(name="Count")
        trend = px.line(trend_df, x="Month", y="Count", color="sentiment", markers=True, title="Monthly Trend Graph")
    else:
        trend = px.line(title="Monthly Trend Graph (No valid dates)")

    cloud_src = keyword_cloud_image(df)
    top_pos, top_neg = top_reviews(df, n=5)
    bi_files = build_bi_exports(df)

    metric_style = {
        "padding": "12px 16px",
        "border": "1px solid #e5e7eb",
        "borderRadius": "10px",
        "background": "#f8fafc",
    }

    total_reviews = len(df)
    pos_pct = round(float((df["sentiment"] == "Positive").mean() * 100), 2) if not df.empty else 0.0
    neg_pct = round(float((df["sentiment"] == "Negative").mean() * 100), 2) if not df.empty else 0.0

    app = Dash(__name__)
    app.layout = html.Div(
        [
            html.H1("Review Sentiment Dashboard (Dash + Plotly)", style={"marginBottom": "6px"}),
            html.P("Includes export-ready datasets for Power BI and Tableau.", style={"marginTop": "0", "color": "#334155"}),

            html.Div(
                [
                    html.Div([html.H4("Total Reviews"), html.H2(f"{total_reviews}")], style=metric_style),
                    html.Div([html.H4("Positive %"), html.H2(f"{pos_pct}%")], style=metric_style),
                    html.Div([html.H4("Negative %"), html.H2(f"{neg_pct}%")], style=metric_style),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(3, minmax(220px, 1fr))", "gap": "12px", "marginBottom": "14px"},
            ),

            dcc.Graph(figure=pie),
            dcc.Graph(figure=trend),

            html.H2("Keyword Cloud", style={"marginTop": "10px"}),
            html.Img(src=cloud_src, style={"width": "100%", "maxWidth": "1100px", "border": "1px solid #e5e7eb", "borderRadius": "10px"})
            if cloud_src
            else html.P("Not enough text to build keyword cloud."),

            html.H2("Top Positive / Negative Reviews", style={"marginTop": "18px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Top Positive Reviews"),
                            dash_table.DataTable(
                                data=top_pos.to_dict("records"),
                                columns=[{"name": col, "id": col} for col in top_pos.columns],
                                style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "fontFamily": "Segoe UI, sans-serif", "fontSize": "13px"},
                                style_table={"overflowX": "auto"},
                                page_size=5,
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.H3("Top Negative Reviews"),
                            dash_table.DataTable(
                                data=top_neg.to_dict("records"),
                                columns=[{"name": col, "id": col} for col in top_neg.columns],
                                style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "fontFamily": "Segoe UI, sans-serif", "fontSize": "13px"},
                                style_table={"overflowX": "auto"},
                                page_size=5,
                            ),
                        ]
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(2, minmax(320px, 1fr))", "gap": "14px"},
            ),

            html.H2("Power BI / Tableau Exports", style={"marginTop": "20px"}),
            html.P("CSV files are saved in dataset/bi_exports and can also be downloaded below."),
            html.Ul([
                html.Li(html.A(filename, href=content, download=filename))
                for filename, content in bi_files.items()
            ]),
        ],
        style={"maxWidth": "1200px", "margin": "20px auto", "fontFamily": "Segoe UI, sans-serif"},
    )
    return app


app = build_app()

if __name__ == "__main__":
    app.run(debug=True, port=8050)
