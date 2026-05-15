def sentiment_chart_data(analytics):
    """Return Chart.js-ready data for sentiment distribution pie chart."""
    return {
        "labels": ["Positive", "Negative", "Neutral"],
        "datasets": [
            {
                "label": "Sentiment Distribution",
                "data": [
                    analytics.get("positive_count", 0),
                    analytics.get("negative_count", 0),
                    analytics.get("neutral_count", 0),
                ],
                "backgroundColor": ["#1f9d67", "#db3a34", "#f4a259"],
                "borderWidth": 1,
            }
        ],
    }


def keyword_chart_data(analytics):
    """Return Chart.js-ready data for keyword frequency bar chart."""
    keywords = analytics.get("most_common_keywords", [])
    return {
        "labels": [item["keyword"] for item in keywords],
        "datasets": [
            {
                "label": "Keyword Frequency",
                "data": [item["count"] for item in keywords],
                "backgroundColor": "#2563eb",
                "borderWidth": 1,
            }
        ],
    }
