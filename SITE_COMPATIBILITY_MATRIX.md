# Website Compatibility Matrix

This matrix shows what your project can analyze, which integration path is used, and what is required for best results.

## Quick Legend
- Status: Good / Medium / Limited
- Mode: API / Scraping / Hybrid

## Compatibility

| Input Type | Example | Mode Used | Current Support | Requirements | Notes |
|---|---|---|---|---|---|
| Google Maps place URL | https://www.google.com/maps/place/... | Hybrid (API first, scrape fallback) | Good | Best with GOOGLE_PLACES_API_KEY | Most reliable source for real business reviews |
| Business name / website URL (for Google lookup) | https://example.com | API first, then website scrape fallback | Good | GOOGLE_PLACES_API_KEY improves hit rate | App derives business query and tries Google Places |
| Direct product review pages | Amazon reviews, Flipkart reviews, Trustpilot pages | Scraping + selectors | Good | No API key required | Better results on direct review pages than generic homepages |
| Generic website homepage | Company homepage with little review content | Scraping + JSON-LD check | Medium | No API key required | Works if page has embedded reviews or visible review blocks |
| Website with JSON-LD reviews | Schema.org Review/Product markup | JSON-LD extraction first | Good | No API key required | Fast and clean extraction path |
| Reddit social mentions | reddit.com/search.json | Public API endpoint | Medium | No token needed (User-Agent required) | Useful for social sentiment signals |
| Facebook comments | Graph API comments endpoint | API | Limited (until configured) | FB_GRAPH_ACCESS_TOKEN + FB_POST_ID | Returns empty if env values are missing |
| Instagram comments | Graph API comments endpoint | API | Limited (until configured) | FB_GRAPH_ACCESS_TOKEN + IG_MEDIA_ID | Returns empty if env values are missing |

## Config Needed For Full Live Data

Set these environment variables (in .env file):

- GOOGLE_PLACES_API_KEY=
- FB_GRAPH_ACCESS_TOKEN=
- FB_POST_ID=
- IG_MEDIA_ID=

Optional tuning:

- REAL_REVIEW_ONLY=true (prefer verified sources)
- MAX_ALLOWED_REVIEWS=300
- ANALYZE_TIME_BUDGET_SECONDS=55
- SCRAPE_TIME_BUDGET_SECONDS=45

## Best Input Recommendations

1. For business review quality: use Google Maps place URL.
2. For ecommerce product sentiment: use direct product review page URLs.
3. For broad signals: use dataset collect with social enabled.
4. Avoid generic homepages when you can provide direct review pages.
