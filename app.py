from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time

# Import ONLY your scraper function
from scraper import scrape_reviews

app = Flask(__name__)
CORS(app)

# ----------------------------
# Health Check Route
# ----------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "message": "Review Scraper API is active"
    })


# ----------------------------
# Scrape Reviews API
# ----------------------------
@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json()

        if not data or "url" not in data:
            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400

        url = data["url"]
        max_reviews = int(data.get("max_reviews", 20))

        start_time = time.time()

        # 🔹 ONLY USE YOUR SELENIUM SCRAPER (NO GOOGLE API)
        reviews = scrape_reviews(url, max_reviews=max_reviews)

        end_time = time.time()

        return jsonify({
            "success": True,
            "url": url,
            "total_reviews": len(reviews),
            "time_taken": round(end_time - start_time, 2),
            "reviews": reviews
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ----------------------------
# Run App (Local Only)
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)