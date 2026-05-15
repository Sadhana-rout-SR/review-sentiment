from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()

def analyze_text(text):
    """Analyze sentiment of text with detailed metrics for reporting."""
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]

    # Classify sentiment based on compound score
    if compound >= 0.05:
        sentiment = "Positive"
    elif compound <= -0.05:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    # Return detailed data for reporting
    return {
        "text": text,
        "sentiment": sentiment,
        "compound_score": compound,
        "positive_score": scores["pos"],
        "negative_score": scores["neg"],
        "neutral_score": scores["neu"],
        "confidence": max(scores["pos"], scores["neg"], scores["neu"]),
    }


def get_sentiment(text):
    """Quick sentiment classification (for compatibility with app.py)."""
    result = analyze_text(text)
    return result["sentiment"]


def get_sentiment_with_scores(text):
    """Get sentiment classification with detailed scoring data for reports."""
    return analyze_text(text)
