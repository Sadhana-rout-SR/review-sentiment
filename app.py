import os
import csv
from functools import wraps
from datetime import datetime, timedelta
from urllib.parse import urlparse
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash
from database import db, configure_database
from scraper import (
    scrape_reviews,
    scrape_google_reviews_with_meta,
    is_review_text,
    extract_page_text_snippets,
    collect_google_original_review_rows,
    collect_website_original_review_rows,
    collect_reddit_social_rows,
    collect_facebook_comment_rows,
    collect_instagram_comment_rows,
)
from sentiment import get_sentiment, analyze_text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
MAX_ALLOWED_REVIEWS = int(os.getenv("MAX_ALLOWED_REVIEWS", "300"))
ANALYZE_TIME_BUDGET_SECONDS = int(os.getenv("ANALYZE_TIME_BUDGET_SECONDS", "55"))
REAL_REVIEW_ONLY = os.getenv("REAL_REVIEW_ONLY", "false").strip().lower() in {"1", "true", "yes", "on"}
ADMIN_BOOTSTRAP_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
ADMIN_BOOTSTRAP_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
DATASET_DIR = Path("datasets")
DATASET_DIR.mkdir(parents=True, exist_ok=True)

database_url = os.getenv("DATABASE_URL", "sqlite:///sentilytics.db").strip()
database_url = configure_database(app)


class AnalysisRun(db.Model):
    __tablename__ = "analysis_runs"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False)
    review_source = db.Column(db.String(32), nullable=False)
    review_source_method = db.Column(db.String(64), nullable=False)
    google_place_name = db.Column(db.String(255), nullable=True)
    google_place_url = db.Column(db.String(2048), nullable=True)
    total_reviews = db.Column(db.Integer, nullable=False, default=0)
    no_real_reviews = db.Column(db.Boolean, nullable=False, default=False)
    warning_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


class ReviewRecord(db.Model):
    __tablename__ = "review_records"

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(16), nullable=False)
    compound_score = db.Column(db.Float, nullable=True, default=0.0)
    positive_score = db.Column(db.Float, nullable=True, default=0.0)
    negative_score = db.Column(db.Float, nullable=True, default=0.0)
    neutral_score = db.Column(db.Float, nullable=True, default=0.0)
    confidence = db.Column(db.Float, nullable=True, default=0.0)
    source_platform = db.Column(db.String(32), nullable=False, default="web")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


def initialize_database():
    try:
        with app.app_context():
            db.create_all()
            ensure_schema_upgrade()
            bootstrap_admin_user()
            sanitize_existing_reviews()
        print("Database initialized.")
    except Exception as exc:
        print(f"Database initialization error: {exc}")


def bootstrap_admin_user():
    """Create a bootstrap admin user if credentials are provided by env variables."""
    if not (ADMIN_BOOTSTRAP_USERNAME and ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD):
        return

    try:
        existing = User.query.filter(
            (User.username == ADMIN_BOOTSTRAP_USERNAME) | (User.email == ADMIN_BOOTSTRAP_EMAIL)
        ).first()
        if existing:
            return

        admin = User(
            username=ADMIN_BOOTSTRAP_USERNAME,
            email=ADMIN_BOOTSTRAP_EMAIL,
            password_hash=generate_password_hash(ADMIN_BOOTSTRAP_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.session.add(admin)
        db.session.commit()
        print("Bootstrap admin account created.")
    except Exception as exc:
        db.session.rollback()
        print(f"bootstrap_admin_user error: {exc}")


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = User.query.filter_by(id=user_id, is_active=True).first()
    return user


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for("auth_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("auth_login", next=request.path))
        if user.role != "admin":
            flash("Admin access is required.", "error")
            return redirect(url_for("index"))
        return view_func(*args, **kwargs)
    return wrapped


@app.before_request
def enforce_login_for_dashboard_and_analysis():
    """Require login for dashboard and analysis workflows without changing route behavior."""
    endpoint = request.endpoint or ""

    # Public/auth endpoints remain accessible without login.
    public_endpoints = {
        "auth_login",
        "auth_register",
        "auth_logout",
        "health",
        "static",
        "analyze",
        "collect_original_reviews",
        "collect_dataset",
    }
    if endpoint in public_endpoints:
        return None

    # If already logged in, allow request.
    if get_current_user():
        return None

    # Return JSON for fetch/AJAX routes so frontend gets a clean auth error.
    json_protected_prefixes = (
        "/analyze",
        "/dataset/",
        "/reviews/",
        "/history",
        "/analytics/",
    )
    if request.path.startswith(json_protected_prefixes):
        return jsonify({"error": "Authentication required. Please login first."}), 401

    flash("Please login to access dashboard and review analysis.", "error")
    return redirect(url_for("auth_login", next=request.path))


def ensure_schema_upgrade():
    """Best-effort schema upgrades for existing databases."""
    statements = [
        "ALTER TABLE review_records ADD COLUMN source_platform VARCHAR(32) DEFAULT 'web'",
        "ALTER TABLE review_records ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE review_records ADD COLUMN compound_score FLOAT DEFAULT 0.0",
        "ALTER TABLE review_records ADD COLUMN positive_score FLOAT DEFAULT 0.0",
        "ALTER TABLE review_records ADD COLUMN negative_score FLOAT DEFAULT 0.0",
        "ALTER TABLE review_records ADD COLUMN neutral_score FLOAT DEFAULT 0.0",
        "ALTER TABLE review_records ADD COLUMN confidence FLOAT DEFAULT 0.0",
    ]
    for stmt in statements:
        try:
            db.session.execute(db.text(stmt))
            db.session.commit()
        except Exception:
            db.session.rollback()


def filter_real_review_texts(texts):
    """Global strict filter used by analyzer, dataset, and persisted counts."""
    cleaned = []
    seen = set()
    for raw in texts or []:
        if not isinstance(raw, str):
            continue
        text = " ".join(raw.split()).strip()
        if not text:
            continue
        if not is_review_text(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def sanitize_existing_reviews():
    """Remove previously stored noisy/fake records and fix run totals for report accuracy."""
    try:
        run_rows = AnalysisRun.query.order_by(AnalysisRun.id.asc()).all()
        changed = 0
        for run in run_rows:
            records = ReviewRecord.query.filter_by(analysis_id=run.id).all()
            valid_records = [r for r in records if is_review_text((r.text or "").strip())]
            if len(valid_records) != len(records):
                valid_ids = {r.id for r in valid_records}
                for rec in records:
                    if rec.id not in valid_ids:
                        db.session.delete(rec)
                changed += 1

            run.total_reviews = len(valid_records)
            if run.total_reviews == 0:
                run.no_real_reviews = True
                if not run.warning_message:
                    run.warning_message = "Historical noisy records removed by strict real-review filter."

        if changed > 0:
            db.session.commit()
        else:
            db.session.rollback()
    except Exception as exc:
        db.session.rollback()
        print(f"sanitize_existing_reviews error: {exc}")


def save_analysis_to_db(url, result_reviews, review_source, review_source_method, google_place_name, google_place_url, no_real_reviews, warning_message):
    try:
        analysis = AnalysisRun(
            url=url,
            review_source=review_source,
            review_source_method=review_source_method,
            google_place_name=google_place_name,
            google_place_url=google_place_url,
            total_reviews=len(result_reviews),
            no_real_reviews=no_real_reviews,
            warning_message=warning_message,
        )
        db.session.add(analysis)
        db.session.flush()

        for item in result_reviews:
            review_row = ReviewRecord(
                analysis_id=analysis.id,
                text=item.get("text", ""),
                sentiment=item.get("sentiment", "Neutral"),
                compound_score=item.get("compound_score", 0.0),
                positive_score=item.get("positive_score", 0.0),
                negative_score=item.get("negative_score", 0.0),
                neutral_score=item.get("neutral_score", 0.0),
                confidence=item.get("confidence", 0.0),
                source_platform=item.get("platform", review_source),
            )
            db.session.add(review_row)

        db.session.commit()
        return analysis.id, "ok"
    except SQLAlchemyError as exc:
        db.session.rollback()
        print(f"Database write error: {exc}")
        return None, "db_write_failed"


def is_valid_http_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def looks_like_review_page_url(url):
    """Heuristic: allow scraping for explicit review/comment/testimonial pages."""
    lowered = (url or "").lower()
    review_hints = [
        "google.com/maps", "goo.gl/maps", "/maps/place",
        "review", "reviews", "rating", "ratings", "testimonial", "testimonials",
        "feedback", "comment", "comments", "customer-review", "product-reviews",
        "all_reviews", "showallreviews", "revpage", "tab=reviews", "filterbystar"
    ]
    return any(hint in lowered for hint in review_hints)


def looks_like_product_page_url(url):
    """Heuristic: allow scraping for common commerce product pages that host reviews."""
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False

    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()

    if any(domain in host for domain in ["amazon.", "flipkart.", "walmart.", "bestbuy.", "newegg."]):
        return any(segment in path for segment in ["/dp/", "/gp/product/", "/product/", "/p/", "/products/"])

    return False


def parse_max_reviews(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 100
    return max(1, min(parsed, MAX_ALLOWED_REVIEWS))


def parse_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_int(value, default, min_value, max_value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(parsed, max_value))


def save_rows_to_csv(url, rows):
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_part = (urlparse(url).netloc or "dataset").replace("www.", "").replace(".", "_")
    filename = f"reviews_dataset_{safe_part}_{timestamp}.csv"
    file_path = DATASET_DIR / filename

    fieldnames = [
        "collected_at_utc",
        "query_url",
        "platform",
        "source_type",
        "author",
        "rating",
        "published_at",
        "text",
        "permalink",
        "place_name",
        "place_url",
    ]

    collected_at = datetime.utcnow().isoformat() + "Z"
    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "collected_at_utc": collected_at,
                "query_url": url,
                "platform": row.get("platform", ""),
                "source_type": row.get("source_type", ""),
                "author": row.get("author", ""),
                "rating": row.get("rating", ""),
                "published_at": row.get("published_at", ""),
                "text": row.get("text", ""),
                "permalink": row.get("permalink", ""),
                "place_name": row.get("place_name", ""),
                "place_url": row.get("place_url", ""),
            })

    return filename


def save_dataset_rows_to_db(url, rows):
    """Persist collected dataset rows as one analysis run with sentiment and timestamps."""
    result_reviews = []
    for row in rows:
        text = row.get("text", "")
        if not text or not is_review_text(text):
            continue
        sentiment_data = analyze_text(text)
        result_reviews.append({
            "text": text,
            "sentiment": sentiment_data["sentiment"],
            "compound_score": sentiment_data["compound_score"],
            "positive_score": sentiment_data["positive_score"],
            "negative_score": sentiment_data["negative_score"],
            "neutral_score": sentiment_data["neutral_score"],
            "confidence": sentiment_data["confidence"],
            "platform": row.get("platform", "social"),
        })

    if not result_reviews:
        return None, "no_rows_to_store"

    return save_analysis_to_db(
        url=url,
        result_reviews=result_reviews,
        review_source="dataset",
        review_source_method="dataset_collect",
        google_place_name="",
        google_place_url="",
        no_real_reviews=False,
        warning_message="",
    )

def get_sentiment_report_data(text):
    """Get detailed sentiment data for reporting purposes."""
    return analyze_text(text)


@app.route("/")
def index():
    return render_template("index.html", current_user=get_current_user())


@app.route("/auth/register", methods=["GET", "POST"])
def auth_register():
    current_user = get_current_user()
    if current_user:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("auth_register.html", current_user=None)
        if "@" not in email or "." not in email:
            flash("Please provide a valid email.", "error")
            return render_template("auth_register.html", current_user=None)
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth_register.html", current_user=None)
        if password != confirm_password:
            flash("Password and confirm password do not match.", "error")
            return render_template("auth_register.html", current_user=None)

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash("Username or email already exists.", "error")
            return render_template("auth_register.html", current_user=None)

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
            is_active=True,
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("auth_login"))

    return render_template("auth_register.html", current_user=None)


@app.route("/auth/login", methods=["GET", "POST"])
def auth_login():
    current_user = get_current_user()
    if current_user:
        return redirect(url_for("index"))

    if request.method == "POST":
        login_value = (request.form.get("login") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter(
            (User.username == login_value) | (User.email == login_value.lower())
        ).first()
        if not user or not user.is_active or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.", "error")
            return render_template("auth_login.html", current_user=None)

        session.clear()
        session["user_id"] = user.id
        session["user_role"] = user.role

        next_url = (request.args.get("next") or "").strip()
        if next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("index"))

    return render_template("auth_login.html", current_user=None)


@app.route("/auth/logout", methods=["GET"])
def auth_logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET"])
@admin_required
def admin_panel():
    total_users = User.query.count()
    total_admins = User.query.filter_by(role="admin").count()
    total_runs = AnalysisRun.query.count()
    total_reviews = ReviewRecord.query.count()
    today_date = datetime.utcnow().date().isoformat()

    runs_today = (
        AnalysisRun.query
        .filter(db.func.date(AnalysisRun.created_at) == today_date)
        .count()
    )

    latest_runs = (
        AnalysisRun.query
        .order_by(AnalysisRun.id.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "admin.html",
        current_user=get_current_user(),
        stats={
            "total_users": total_users,
            "total_admins": total_admins,
            "total_runs": total_runs,
            "total_reviews": total_reviews,
            "runs_today": runs_today,
        },
        latest_runs=latest_runs,
    )


@app.route("/health", methods=["GET"])
def health():
    has_places_key = bool(os.getenv("GOOGLE_PLACES_API_KEY", "").strip())
    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    return jsonify({
        "status": "ok",
        "google_places_api_configured": has_places_key,
        "max_allowed_reviews": MAX_ALLOWED_REVIEWS,
        "real_review_only": REAL_REVIEW_ONLY,
        "database": db_status,
        "database_url": app.config["SQLALCHEMY_DATABASE_URI"]
    })


@app.route("/history", methods=["GET"])
def history():
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 100))
        runs = (
            AnalysisRun.query
            .order_by(AnalysisRun.id.desc())
            .limit(limit)
            .all()
        )

        payload = []
        for run in runs:
            payload.append({
                "analysis_id": run.id,
                "url": run.url,
                "review_source": run.review_source,
                "review_source_method": run.review_source_method,
                "total_reviews": run.total_reviews,
                "no_real_reviews": run.no_real_reviews,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            })

        return jsonify({"history": payload})
    except Exception as exc:
        return jsonify({"error": f"Unable to fetch history: {exc}"}), 500


@app.route("/analytics/daily", methods=["GET"])
def analytics_daily():
    try:
        days = parse_int(request.args.get("days", 14), default=14, min_value=3, max_value=90)
        verified_only = parse_bool(request.args.get("verified_only", "true"), default=True)
        include_website = parse_bool(request.args.get("include_website", "true"), default=True)
        start_date = (datetime.utcnow() - timedelta(days=days - 1)).date()

        runs_query = AnalysisRun.query.filter(
            AnalysisRun.total_reviews > 0,
            AnalysisRun.no_real_reviews.is_(False),
        )

        if verified_only:
            allowed_methods = ["google_places_api", "google_maps_scraping", "dataset_collect"]
            if include_website:
                allowed_methods.append("website_scraping")
            runs_query = runs_query.filter(AnalysisRun.review_source_method.in_(allowed_methods))

        run_ids_subquery = runs_query.with_entities(AnalysisRun.id).subquery()

        rows = (
            db.session.query(
                db.func.date(AnalysisRun.created_at).label("day"),
                db.func.count(db.distinct(AnalysisRun.id)).label("runs"),
                db.func.count(ReviewRecord.id).label("reviews"),
                db.func.sum(db.case((ReviewRecord.sentiment == "Positive", 1), else_=0)).label("positive"),
                db.func.sum(db.case((ReviewRecord.sentiment == "Negative", 1), else_=0)).label("negative"),
                db.func.sum(db.case((ReviewRecord.sentiment == "Neutral", 1), else_=0)).label("neutral"),
            )
            .outerjoin(ReviewRecord, ReviewRecord.analysis_id == AnalysisRun.id)
            .filter(AnalysisRun.id.in_(run_ids_subquery))
            .filter(db.func.date(AnalysisRun.created_at) >= start_date.isoformat())
            .group_by(db.func.date(AnalysisRun.created_at))
            .order_by(db.func.date(AnalysisRun.created_at).asc())
            .all()
        )

        by_day = {}
        for row in rows:
            day = str(row.day)
            by_day[day] = {
                "date": day,
                "runs": int(row.runs or 0),
                "reviews": int(row.reviews or 0),
                "positive": int(row.positive or 0),
                "negative": int(row.negative or 0),
                "neutral": int(row.neutral or 0),
            }

        series = []
        for offset in range(days):
            day_obj = start_date + timedelta(days=offset)
            day_str = day_obj.isoformat()
            item = by_day.get(day_str, {
                "date": day_str,
                "runs": 0,
                "reviews": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
            })
            series.append(item)

        total_reviews = sum(item["reviews"] for item in series)
        avg_daily_reviews = round(total_reviews / len(series), 2) if series else 0
        today_reviews = series[-1]["reviews"] if series else 0
        yesterday_reviews = series[-2]["reviews"] if len(series) > 1 else 0

        if yesterday_reviews > 0:
            growth_pct = round(((today_reviews - yesterday_reviews) / yesterday_reviews) * 100, 2)
        elif today_reviews > 0:
            growth_pct = 100.0
        else:
            growth_pct = 0.0

        return jsonify({
            "days": days,
            "verified_only": verified_only,
            "include_website": include_website,
            "daily": series,
            "summary": {
                "total_reviews": total_reviews,
                "avg_daily_reviews": avg_daily_reviews,
                "today_reviews": today_reviews,
                "yesterday_reviews": yesterday_reviews,
                "growth_pct": growth_pct,
            },
        })
    except Exception as exc:
        return jsonify({"error": f"Unable to fetch daily analytics: {exc}"}), 500


@app.route("/dataset/collect", methods=["POST"])
def collect_dataset():
    try:
        url = (request.form.get("url") or "").strip()
        max_reviews = parse_max_reviews(request.form.get("max_reviews", 100))
        include_social = parse_bool(request.form.get("include_social", "true"), default=True)
        include_website = parse_bool(request.form.get("include_website", "true"), default=True)

        if not url:
            return jsonify({"error": "URL is required"}), 400
        if not is_valid_http_url(url):
            return jsonify({"error": "Please provide a valid http/https URL"}), 400

        google_payload = collect_google_original_review_rows(url, max_reviews=max_reviews)
        google_rows = google_payload.get("rows", [])
        website_payload = {"rows": [], "reason": "disabled"}
        website_rows = []
        if include_website:
            website_payload = collect_website_original_review_rows(url, max_reviews=max_reviews)
            website_rows = website_payload.get("rows", [])

        social_rows = []
        facebook_rows = []
        instagram_rows = []
        if include_social:
            social_rows = collect_reddit_social_rows(url, max_items=max_reviews)
            facebook_rows = collect_facebook_comment_rows(max_items=max_reviews)
            instagram_rows = collect_instagram_comment_rows(max_items=max_reviews)

        rows = website_rows + google_rows + social_rows + facebook_rows + instagram_rows
        if not rows:
            return jsonify({
                "error": "No original review rows collected from website/Google/social sources",
                "google_reason": google_payload.get("reason", "unknown"),
                "website_reason": website_payload.get("reason", "unknown"),
            }), 404

        filename = save_rows_to_csv(url, rows)
        analysis_id, db_write_status = save_dataset_rows_to_db(url, rows)
        return jsonify({
            "message": "Dataset CSV created",
            "analysis_id": analysis_id,
            "db_write_status": db_write_status,
            "filename": filename,
            "download_url": f"/dataset/download/{filename}",
            "total_rows": len(rows),
            "website_rows": len(website_rows),
            "google_rows": len(google_rows),
            "social_rows": len(social_rows) + len(facebook_rows) + len(instagram_rows),
            "reddit_rows": len(social_rows),
            "facebook_rows": len(facebook_rows),
            "instagram_rows": len(instagram_rows),
            "google_reason": google_payload.get("reason", "ok"),
            "website_reason": website_payload.get("reason", "ok"),
        })
    except Exception as exc:
        return jsonify({"error": f"Dataset collection failed: {exc}"}), 500


@app.route("/reviews/collect", methods=["POST"])
def collect_original_reviews():
    """Collect original customer reviews for a URL and return rows for UI display."""
    try:
        url = (request.form.get("url") or "").strip()
        max_reviews = parse_max_reviews(request.form.get("max_reviews", 100))

        if not url:
            return jsonify({"error": "URL is required"}), 400
        if not is_valid_http_url(url):
            return jsonify({"error": "Please provide a valid http/https URL"}), 400

        website_payload = collect_website_original_review_rows(url, max_reviews=max_reviews)
        website_rows = website_payload.get("rows", [])

        google_payload = {"rows": [], "reason": "not_attempted"}
        google_rows = []
        if not website_rows:
            google_payload = collect_google_original_review_rows(url, max_reviews=max_reviews)
            google_rows = google_payload.get("rows", [])

        rows = website_rows if website_rows else google_rows
        source = "website" if website_rows else "google"
        source_reason = website_payload.get("reason", "") if website_rows else google_payload.get("reason", "")

        if not rows:
            return jsonify({
                "error": "No original customer reviews found for this URL",
                "website_reason": website_payload.get("reason", "unknown"),
                "google_reason": google_payload.get("reason", "unknown"),
            }), 404

        analysis_id, db_write_status = save_dataset_rows_to_db(url, rows)
        return jsonify({
            "message": "Original customer reviews collected",
            "analysis_id": analysis_id,
            "db_write_status": db_write_status,
            "rows": rows,
            "total_rows": len(rows),
            "source": source,
            "source_reason": source_reason,
            "website_reason": website_payload.get("reason", "unknown"),
            "google_reason": google_payload.get("reason", "unknown"),
        })
    except Exception as exc:
        return jsonify({"error": f"Original review collection failed: {exc}"}), 500


@app.route("/dataset/download/<path:filename>", methods=["GET"])
def download_dataset(filename):
    try:
        return send_from_directory(DATASET_DIR.resolve(), filename, as_attachment=True)
    except Exception as exc:
        return jsonify({"error": f"Unable to download dataset: {exc}"}), 404


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        started_at = datetime.utcnow()
        url = (request.form.get("url") or "").strip()
        max_reviews = parse_max_reviews(request.form.get("max_reviews", 100))

        if not url:
            return jsonify({"error": "URL is required"}), 400

        if not is_valid_http_url(url):
            return jsonify({"error": "Please provide a valid http/https URL"}), 400

        # Always try real Google reviews first for any website URL.
        google_result = scrape_google_reviews_with_meta(url, max_reviews)
        url_review_texts = google_result.get("reviews", [])
        review_source = "google"
        review_source_method = google_result.get("method", "google_not_found")
        review_source_reason = google_result.get("reason", "")
        google_place_name = google_result.get("place_name", "")
        google_place_url = google_result.get("place_url", "")

        # In strict mode, only allow website fallback for clear review-page URLs.
        allow_website_fallback = (
            (not REAL_REVIEW_ONLY)
            or looks_like_review_page_url(url)
            or looks_like_product_page_url(url)
        )

        # Fallback to website reviews only when Google reviews are not found.
        elapsed = (datetime.utcnow() - started_at).total_seconds()
        if allow_website_fallback and (not url_review_texts) and elapsed < ANALYZE_TIME_BUDGET_SECONDS:
            website_payload = collect_website_original_review_rows(url, max_reviews=max_reviews)
            website_rows = website_payload.get("rows", [])
            url_review_texts = [row.get("text", "") for row in website_rows if row.get("text")]
            review_source = "website"
            review_source_method = "website_scraping"
            review_source_reason = website_payload.get("reason", "review_page_fallback" if REAL_REVIEW_ONLY else "")
            google_place_name = ""
            google_place_url = ""
        elif (not url_review_texts) and elapsed >= ANALYZE_TIME_BUDGET_SECONDS:
            review_source_reason = "time_budget_exceeded"

        raw_count = len(url_review_texts)
        url_review_texts = filter_real_review_texts(url_review_texts)
        filtered_count = len(url_review_texts)

        used_page_fallback = False
        if filtered_count == 0:
            fallback_texts = extract_page_text_snippets(url, max_items=min(max_reviews, 24))
            if fallback_texts:
                url_review_texts = fallback_texts
                raw_count = len(fallback_texts)
                filtered_count = len(fallback_texts)
                review_source = "website"
                review_source_method = "page_text_fallback"
                review_source_reason = "no_reviews_found"
                used_page_fallback = True

        warning_message = ""
        no_real_reviews = False
        if used_page_fallback:
            no_real_reviews = True
            warning_message = (
                "No review content was found for this URL. "
                "Showing sentiment for readable page text instead."
            )
        elif raw_count > 0 and filtered_count == 0:
            no_real_reviews = True
            warning_message = (
                "No real customer reviews found for this URL. "
                "Detected text looked like menu/navigation content. "
                "Try another business URL or connect Google Places API key for official Google reviews."
            )
        elif REAL_REVIEW_ONLY and raw_count == 0:
            no_real_reviews = True
            if looks_like_review_page_url(url):
                warning_message = (
                    "This looks like a review page URL, but no readable customer reviews were extracted. "
                    "Try the exact product/customer review page or increase max reviews."
                )
            else:
                warning_message = (
                    "Real-review-only mode is enabled. "
                    "Use direct review-page URLs (Amazon/Flipkart review pages) or add valid Google/social API keys."
                )
        elif raw_count == 0 and review_source == "google" and review_source_method == "google_not_found":
            no_real_reviews = True
            if review_source_reason == "invalid_or_missing_api_key":
                warning_message = (
                    "Google review API key is missing/invalid. "
                    "Set a real GOOGLE_PLACES_API_KEY (not YOUR_API_KEY) and try again."
                )
            elif review_source_reason == "time_budget_exceeded":
                warning_message = (
                    "Time budget exceeded for this URL. "
                    "Reduce max reviews or retry with a more specific business URL."
                )
            else:
                warning_message = (
                    "Google reviews were not found for this website right now. "
                    "Try a direct Google Maps place/review URL or use a valid Google Places API key."
                )

        result_reviews = [analyze_text(txt) for txt in url_review_texts]
        analysis_id, db_write_status = save_analysis_to_db(
            url=url,
            result_reviews=result_reviews,
            review_source=review_source,
            review_source_method=review_source_method,
            google_place_name=google_place_name,
            google_place_url=google_place_url,
            no_real_reviews=no_real_reviews,
            warning_message=warning_message,
        )

        return jsonify({
            "analysis_id": analysis_id,
            "db_write_status": db_write_status,
            "url_review_texts": url_review_texts,
            "url_reviews": result_reviews,
            "raw_count": raw_count,
            "filtered_count": filtered_count,
            "review_source": review_source,
            "review_source_method": review_source_method,
            "review_source_reason": review_source_reason,
            "real_review_only": REAL_REVIEW_ONLY,
            "google_place_name": google_place_name,
            "google_place_url": google_place_url,
            "no_real_reviews": no_real_reviews,
            "warning_message": warning_message
        })

    except Exception as e:
        print("DEBUG REVIEWS:", url_review_texts)
        return jsonify({"error": "Internal server error while analyzing reviews"}), 500
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)