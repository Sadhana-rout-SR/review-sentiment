from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class SentimentModel:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    def classify(self, text: str):
        """Classify a single review into Positive, Negative, or Neutral with score details."""
        scores = self.analyzer.polarity_scores(text)
        compound = scores["compound"]

        if compound >= 0.05:
            sentiment = "Positive"
        elif compound <= -0.05:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        return {
            "sentiment": sentiment,
            "compound": compound,
            "positive_score": scores["pos"],
            "negative_score": scores["neg"],
            "neutral_score": scores["neu"],
        }

    def analyze_reviews(self, review_rows):
        """Attach sentiment metrics to every review row."""
        analyzed = []
        for row in review_rows:
            text = row.get("text", "")
            sentiment = self.classify(text)
            merged = dict(row)
            merged.update(sentiment)
            analyzed.append(merged)
        return analyzed
