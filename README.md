# Sentilytics - Social & Google Review Sentiment Analyzer

Sentilytics is a Flask-based AI sentiment dashboard that analyzes customer review text from:

- Google reviews (official Places API when configured)
- Google Maps scraping fallback
- Website review scraping fallback

It classifies reviews into Positive, Negative, and Neutral using VADER sentiment.

## Source Compatibility

For a quick overview of which website/source types are best supported (API vs scraping), see:

- [SITE_COMPATIBILITY_MATRIX.md](SITE_COMPATIBILITY_MATRIX.md)

## Features

- Analyze any website URL
- Prefer official Google reviews via Places API
- Fallback to Google Maps reading and website scraping
- Strict filtering for real review-like text (rejects menu/navigation noise)
- Review source transparency in UI:
  - Google Reviews (Official API)
  - Google Reviews (Maps Read)
  - Website Reviews
- Reports with stats and CSV export
- Light/Dark theme
- Database persistence for analysis history

## Project Structure

```text
app.py
scraper.py
sentiment.py
templates/
  index.html
static/
  style.css
requirements.txt
.env.example
README.md
```

## Requirements

- Python 3.10+
- Google Chrome installed (for Selenium fallback)

## Setup

1. Create virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` and set values.

4. Run app:

```powershell
python app.py
```

Open: `http://127.0.0.1:5000`

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_PLACES_API_KEY` | Recommended | Official Google Places API key for real Google reviews |
| `MAX_ALLOWED_REVIEWS` | Optional | Server-side upper limit for `max_reviews` input (default: `300`) |
| `DATABASE_URL` | Optional | SQLAlchemy DB URL (default: `sqlite:///sentilytics.db`) |
| `ANALYZE_TIME_BUDGET_SECONDS` | Optional | Target request time budget (default: `55`) |
| `SCRAPE_TIME_BUDGET_SECONDS` | Optional | Browser scraping budget (default: `45`) |
| `REAL_REVIEW_ONLY` | Optional | `true` (default) allows only verified sources; disables website fallback |
| `FB_GRAPH_ACCESS_TOKEN` | Optional | Required for official Facebook/Instagram comment API |
| `FB_POST_ID` | Optional | Facebook post ID for comments collection |
| `IG_MEDIA_ID` | Optional | Instagram media ID for comments collection |

MySQL example:

```text
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/sentilytics
```

## API Endpoints

### `GET /health`
Returns service status and configuration summary.

Example response:

```json
{
  "status": "ok",
  "google_places_api_configured": true,
  "max_allowed_reviews": 300,
  "database": "ok",
  "database_url": "sqlite:///sentilytics.db"
}
```

### `GET /history?limit=20`
Returns recent analysis history from database.

### `GET /analytics/daily?days=14`
Returns day-wise analytics from database including:

- daily review count
- day-wise Positive/Negative/Neutral counts
- summary KPIs: today reviews, yesterday reviews, growth percentage, average daily reviews

### `POST /dataset/collect`
Collects original-review dataset rows and saves CSV in local `datasets/` folder.

Form fields:

- `url` (required)
- `max_reviews` (optional)
- `include_social` (optional, default: `true`)

Sources used:

- Google original reviews via Places API
- Social media rows via Reddit public search
- Facebook comments via Graph API (when token + post ID configured)
- Instagram comments via Graph API (when token + media ID configured)

Response includes `download_url`, row counts, and generated filename.

### `GET /dataset/download/<filename>`
Downloads a generated dataset CSV file.

### `POST /analyze`
Form fields:

- `url` (required)
- `max_reviews` (optional)

Response fields include:

- `url_reviews`: analyzed reviews with sentiment
- `review_source`: `google` or `website`
- `review_source_method`: `google_places_api`, `google_maps_scraping`, `website_scraping`, etc.
- `google_place_name`, `google_place_url`
- `no_real_reviews`, `warning_message`

## Important Notes

- For best quality and compliance, use the official Places API key.
- Scraping-based methods can break when site/Google UI changes.
- If no genuine reviews are found, app returns warning instead of fake menu text.

## Troubleshooting

- If no Google reviews are returned:
  - Verify `GOOGLE_PLACES_API_KEY`
  - Ensure Places API is enabled in Google Cloud
  - Check billing/project restrictions
- If Selenium fails:
  - Update Chrome browser
  - Reinstall dependencies

## Future Enhancements

- Add reviewer metadata (author/rating/time)
- Add multilingual sentiment model
- Add scheduled background ingestion
