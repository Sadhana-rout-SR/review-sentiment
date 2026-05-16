# scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import re
import os
from datetime import datetime, timezone
import requests
from urllib.parse import urlparse, quote_plus, urljoin
from bs4 import BeautifulSoup

MAX_SCROLLS = 30
WAIT_TIME = 2


def _scrape_time_budget_seconds():
    try:
        return max(15, int(os.getenv("SCRAPE_TIME_BUDGET_SECONDS", "45")))
    except Exception:
        return 45

# Enhanced review extraction patterns
REVIEW_PATTERNS = [
    # Generic review containers
    "//div[contains(@class, 'review')]",
    "//div[contains(@class, 'testimonial')]",
    "//div[contains(@class, 'feedback')]",
    "//div[contains(@class, 'comment')]",
    "//article[contains(@class, 'review')]",
    "//section[contains(@class, 'review')]",

    # Specific platform selectors
    "//div[contains(@class, 'review-content')]",
    "//div[contains(@class, 'review-text')]",
    "//div[contains(@class, 'review-body')]",
    "//div[contains(@class, 'customer-review')]",
    "//div[contains(@class, 'user-review')]",
    "//div[contains(@class, 'review-entry')]",
    "//div[contains(@data-testid, 'review')]",
    "//div[contains(@data-cy, 'review')]",

    # Google Reviews
    "//div[contains(@class, 'gws-localreviews__google-review')]",
    "//div[contains(@class, 'review-full-text')]",

    # Yelp
    "//div[contains(@class, 'review-content')]",
    "//p[contains(@class, 'comment__text')]",

    # Trustpilot
    "//div[contains(@class, 'review-content__text')]",
    "//p[contains(@class, 'review-content__text')]",

    # Amazon
    "//div[contains(@class, 'review-text-content')]",
    "//span[contains(@class, 'review-text')]",

    # Common review text patterns
    "//*[contains(text(),'review')]/following-sibling::*",
    "//*[contains(text(),'testimonial')]/following-sibling::*",
    "//*[contains(text(),'feedback')]/following-sibling::*",
]

# Keywords that indicate customer reviews
REVIEW_KEYWORDS = [
    "customer", "client", "user", "buyer", "purchaser", "consumer",
    "testimonial", "feedback", "review", "experience", "service",
    "product", "quality", "recommend", "satisfied", "dissatisfied",
    "excellent", "terrible", "amazing", "awful", "great", "poor",
    "love", "hate", "best", "worst", "helpful", "unhelpful"
]

NAVIGATION_NOISE_TERMS = [
    "sign in", "sign up", "my account", "your account", "orders", "order history",
    "wishlist", "cart", "customer service", "returns", "track package", "prime video",
    "best sellers", "gift cards", "registry", "subscribe", "membership", "browsing history",
    "recommendations", "new customer", "start here", "shop now", "all categories",
    "search settings", "advanced search", "your data in search", "search history",
    "send feedback", "dark theme", "advertising", "business", "how search works",
    "privacy", "terms", "settings"
]


def _looks_like_navigation_noise(text_lower):
    hits = sum(1 for term in NAVIGATION_NOISE_TERMS if term in text_lower)
    return hits >= 2


def _extract_candidate_review_links(base_url, page_source, limit=6):
    """Find likely internal review URLs to improve extraction on non-review landing pages."""
    try:
        parsed_base = urlparse(base_url)
        base_host = parsed_base.netloc.lower().replace("www.", "")
        soup = BeautifulSoup(page_source, "html.parser")
        candidates = []
        seen = set()

        keywords = [
            "review", "reviews", "rating", "ratings", "testimonial", "feedback",
            "customer-review", "product-reviews", "all_reviews", "showallreviews",
            "comments", "opinions",
        ]

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            text = (a.get_text(" ", strip=True) or "").lower()
            if not href:
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            host = parsed.netloc.lower().replace("www.", "")
            if host and host != base_host:
                continue

            target = full_url.lower()
            if any(k in target for k in keywords) or any(k in text for k in keywords):
                key = full_url.split("#")[0]
                if key not in seen:
                    seen.add(key)
                    candidates.append(key)
            if len(candidates) >= limit:
                break

        return candidates[:limit]
    except Exception:
        return []

def is_review_text(text):
    """Check if text looks like a customer review"""
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return False

    text_lower = compact.lower()
    words = re.findall(r"[a-zA-Z']+", text_lower)
    word_count = len(words)

    # Keep reasonable sentence length for review snippets.
    if word_count < 4 or word_count > 220:
        return False

    if len(compact) < 20:
        return False

    # Reject obvious navigation/account noise.
    if _looks_like_navigation_noise(text_lower):
        return False

    # Strong non-review markers (treat as noise only when dominant).
    skip_patterns = [
        "privacy policy", "terms of service", "cookie policy", "all rights reserved",
        "sign in", "sign up", "create account", "forgot password", "add to cart",
        "track order", "customer service", "contact us", "help center"
    ]
    skip_hits = sum(1 for skip in skip_patterns if skip in text_lower)

    # Compute light intent signals.
    keyword_count = sum(1 for keyword in REVIEW_KEYWORDS if keyword in text_lower)
    has_sentence_shape = any(mark in compact for mark in [".", "!", "?"])

    # Use whole-word checks to avoid substring false positives (e.g. "i" in "digital").
    experience_words = {"i", "we", "my", "our", "me", "us", "customer", "user", "client", "bought", "purchased"}
    opinion_words = {"good", "bad", "great", "terrible", "excellent", "awful", "amazing", "worst", "best", "love", "hate", "recommend", "would", "should", "poor", "quality"}
    word_set = set(words)
    has_personal = any(word in word_set for word in experience_words)
    has_opinion = any(word in word_set for word in opinion_words)

    # Ratings/stars are strong review indicators even without keywords.
    has_rating_signal = bool(
        re.search(r"\b([1-5](?:\.0)?\s*/\s*5|[1-5]\s*stars?|\d{1,2}%\s*(?:off|satisfied))\b", text_lower)
    )

    if skip_hits >= 2 and not (has_personal or has_opinion or has_rating_signal or keyword_count >= 1):
        return False

    # Accept if we have at least one strong review intent signal.
    return has_sentence_shape or has_personal or has_opinion or has_rating_signal or keyword_count >= 1

# 🔹 Enhanced: Extract JSON-LD reviews (Schema.org)
def extract_jsonld_reviews(page_source):
    reviews = []
    soup = BeautifulSoup(page_source, "html.parser")

    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                data = [data]

            for item in data:
                # Direct reviews
                if item.get("@type") == "Review":
                    review_text = item.get("reviewBody", "") or item.get("description", "")
                    if review_text and len(review_text) > 20:
                        reviews.append(review_text)

                # Product reviews
                if item.get("@type") == "Product" and "review" in item:
                    for r in item["review"]:
                        review_text = r.get("reviewBody", "") or r.get("description", "")
                        if review_text and len(review_text) > 20:
                            reviews.append(review_text)

                # Organization reviews
                if item.get("@type") == "Organization" and "review" in item:
                    for r in item["review"]:
                        review_text = r.get("reviewBody", "") or r.get("description", "")
                        if review_text and len(review_text) > 20:
                            reviews.append(review_text)

        except Exception as e:
            print(f"JSON-LD parsing error: {e}")
            continue

    return list(set(reviews))  # Remove duplicates

# 🔹 Enhanced: Extract reviews using multiple strategies (optimized)
def extract_structured_reviews(driver):
    reviews = set()

    # Use only the most effective patterns to avoid performance issues
    effective_patterns = [
        "//div[contains(@class, 'review') and string-length(text()) > 50]",
        "//div[contains(@class, 'testimonial') and string-length(text()) > 50]",
        "//div[contains(@class, 'feedback') and string-length(text()) > 50]",
        "//div[contains(@class, 'comment') and string-length(text()) > 50]",
        "//article[contains(@class, 'review')]",
        "//section[contains(@class, 'review')]",
        "//div[contains(@class, 'review-content')]",
        "//div[contains(@class, 'review-text')]",
        "//div[contains(@class, 'customer-review')]",
        "//div[contains(@class, 'user-review')]",
    ]

    for pattern in effective_patterns:
        try:
            # Add timeout to prevent hanging
            elements = driver.find_elements(By.XPATH, pattern)
            for element in elements:
                try:
                    text = element.text.strip()
                    if text and len(text) > 30 and len(text) < 2000 and is_review_text(text):
                        reviews.add(text)
                except:
                    continue
        except Exception as e:
            continue  # Skip failed selectors

    return reviews

# 🔹 Enhanced: Extract reviews from common review platforms
def extract_platform_reviews(driver, url):
    reviews = set()
    url_lower = url.lower()

    try:
        # Google Reviews - Enhanced approach
        if "google.com" in url_lower:
            print("Detected Google - using enhanced extraction")
            try:
                time.sleep(3)

                # For Google Maps or business pages
                if "maps" in url_lower or "/place/" in url_lower:
                    print("Extracting Google Maps reviews...")

                    # Google Maps specific selectors
                    maps_selectors = [
                        "//div[contains(@class, 'review-content')]",
                        "//div[contains(@class, 'review-full-text')]",
                        "//span[contains(@class, 'review-text')]",
                        "//div[contains(@class, 'section-review-text')]",
                        "//div[contains(@data-review-id)]//div[contains(@class, 'text')]",
                        "//div[contains(@jsaction, 'review')]//div[contains(@class, 'text')]"
                    ]

                    for selector in maps_selectors:
                        try:
                            elements = driver.find_elements(By.XPATH, selector)
                            for elem in elements:
                                text = elem.text.strip()
                                if text and len(text) > 20 and len(text) < 2000 and is_review_text(text):
                                    reviews.add(text)
                        except:
                            continue

                # For Google Search results with reviews
                elif "search" in url_lower:
                    print("Extracting Google search review snippets...")

                    # Search results specific selectors
                    search_selectors = [
                        "//div[contains(@class, 'gws-localreviews__google-review')]",
                        "//div[contains(@class, 'review-snippet')]",
                        "//span[contains(@class, 'review-text')]",
                        "//div[contains(@class, 'review-content')]",
                        "//div[contains(@data-ved) and contains(@class, 'review')]",
                        "//div[contains(@class, 'aCOpRe')]//span",  # Common Google review container
                        "//div[contains(@class, 'Jtu6Td')]//span"   # Another common container
                    ]

                    for selector in search_selectors:
                        try:
                            elements = driver.find_elements(By.XPATH, selector)
                            for elem in elements:
                                text = elem.text.strip()
                                if text and len(text) > 30 and len(text) < 1000 and is_review_text(text):
                                    reviews.add(text)
                        except:
                            continue

                # Scroll to load more reviews
                for i in range(5):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

                    # Try to click "More reviews" or similar buttons
                    try:
                        more_buttons = driver.find_elements(By.XPATH,
                            "//button[contains(text(), 'More') or contains(text(), 'reviews') or contains(@aria-label, 'More')]")
                        for button in more_buttons:
                            if button.is_displayed():
                                button.click()
                                time.sleep(2)
                                break
                    except:
                        pass

                print(f"Found {len(reviews)} Google reviews")

            except Exception as e:
                print(f"Google extraction error: {e}")

        # Yelp
        elif "yelp.com" in url_lower:
            print("Detected Yelp - using specialized extraction")
            review_elements = driver.find_elements(By.XPATH,
                "//div[contains(@class, 'review-content')]//p | //p[contains(@class, 'comment__text')] | //div[contains(@class, 'review-wrapper')]")
            for elem in review_elements:
                text = elem.text.strip()
                if text and len(text) > 20:
                    reviews.add(text)

        # Trustpilot
        elif "trustpilot.com" in url_lower:
            print("Detected Trustpilot - using specialized extraction")
            review_elements = driver.find_elements(By.XPATH,
                "//div[contains(@class, 'review-content__text')] | //p[contains(@class, 'review-content__text')] | //div[contains(@class, 'review-card__text')]")
            for elem in review_elements:
                text = elem.text.strip()
                if text and len(text) > 20:
                    reviews.add(text)

        # Amazon - Enhanced selectors
        elif "amazon.com" in url_lower or "amazon.in" in url_lower:
            print("Detected Amazon - using enhanced extraction")
            try:
                # Wait for dynamic content to load
                time.sleep(3)

                # Multiple selector strategies for Amazon reviews
                amazon_selectors = [
                    "//div[contains(@class, 'review-text-content')]/span",
                    "//span[contains(@class, 'review-text')]",
                    "//div[contains(@data-hook, 'review-collapsed')]//span",
                    "//div[contains(@class, 'a-expander-content') and contains(@class, 'review-text-content')]//span",
                    "//span[contains(@data-hook, 'review-body')]",
                    "//div[contains(@class, 'reviewText')]",
                    "//div[contains(@id, 'customer_review-')]//div[contains(@class, 'review-text')]",
                ]

                for selector in amazon_selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if text and len(text) > 20 and len(text) < 2000 and is_review_text(text):
                                reviews.add(text)
                    except:
                        continue

                # Try to expand collapsed reviews
                try:
                    expand_buttons = driver.find_elements(By.XPATH,
                        "//a[contains(@class, 'a-expander-header') or contains(text(), 'Read more')]")
                    for button in expand_buttons:
                        try:
                            if button.is_displayed():
                                button.click()
                                time.sleep(1)
                        except:
                            pass
                except:
                    pass

                # Additional scroll for Amazon
                for i in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

                print(f"Found {len(reviews)} Amazon reviews")

            except Exception as e:
                print(f"Amazon extraction error: {e}")

        # Flipkart
        elif "flipkart.com" in url_lower:
            print("Detected Flipkart - using specialized extraction")
            review_elements = driver.find_elements(By.XPATH,
                "//div[contains(@class, 't-ZTKy')] | //p[contains(@class, '_2-N8zT')] | //div[contains(@class, 'qwjRop')] | //div[contains(@class, 'ZmyHeo')]")
            for elem in review_elements:
                text = elem.text.strip()
                if text and len(text) > 20:
                    reviews.add(text)

        # TripAdvisor
        elif "tripadvisor.com" in url_lower:
            print("Detected TripAdvisor - using specialized extraction")
            review_elements = driver.find_elements(By.XPATH,
                "//div[contains(@class, 'review-container')] | //p[contains(@class, 'partial_entry')] | //span[contains(@class, 'review-text')]")
            for elem in review_elements:
                text = elem.text.strip()
                if text and len(text) > 20:
                    reviews.add(text)

        # Generic review extraction for other sites
        else:
            print("Using enhanced generic review extraction")
            # Look for review containers with multiple strategies
            review_selectors = [
                # Standard review classes
                "//div[contains(@class, 'review') and string-length(text()) > 50]",
                "//div[contains(@class, 'testimonial') and string-length(text()) > 50]",
                "//div[contains(@class, 'feedback') and string-length(text()) > 50]",
                "//article[contains(@class, 'review')]",
                "//section[contains(@class, 'review')]",
                "//blockquote[contains(@class, 'review')]",
                "//div[contains(@id, 'review') and string-length(text()) > 50]",
                "//div[contains(@data-type, 'review')]",

                # Common e-commerce review patterns
                "//div[contains(@class, 'customer-review')]",
                "//div[contains(@class, 'user-review')]",
                "//div[contains(@class, 'review-content')]",
                "//div[contains(@class, 'review-text')]",
                "//div[contains(@class, 'review-body')]",
                "//p[contains(@class, 'review')]",

                # Comment and feedback patterns
                "//div[contains(@class, 'comment') and string-length(text()) > 50]",
                "//div[contains(@class, 'feedback') and string-length(text()) > 50]",
                "//article[contains(@class, 'comment')]",

                # Rating and review combinations
                "//div[contains(@class, 'rating') and contains(@class, 'review')]",
                "//div[contains(@data-rating) and string-length(text()) > 30]",

                # Generic content blocks that might contain reviews
                "//div[string-length(text()) > 100 and string-length(text()) < 2000 and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'customer')]",
                "//div[string-length(text()) > 100 and string-length(text()) < 2000 and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'experience')]",
            ]

            for selector in review_selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text and is_review_text(text):
                            reviews.add(text)
                except:
                    continue

            # If still no reviews, try broader search with better filtering
            if not reviews:
                print("Trying broader review search...")
                broad_elements = driver.find_elements(By.XPATH,
                    "//div[string-length(text()) > 100 and string-length(text()) < 2000]")

                for elem in broad_elements:
                    text = elem.text.strip()
                    if is_review_text(text):
                        reviews.add(text)

            # Additional scroll for dynamic content
            if len(reviews) < 5:
                print("Scrolling for more potential reviews...")
                for i in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

                    # Look for "Load more" or "Show more" buttons
                    try:
                        load_buttons = driver.find_elements(By.XPATH,
                            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more') or contains(@class, 'load-more')]")
                        for button in load_buttons:
                            if button.is_displayed():
                                button.click()
                                time.sleep(2)
                                break
                    except:
                        pass

    except Exception as e:
        print(f"Platform-specific extraction error: {e}")

    return reviews

# 🔹 Enhanced: Fallback content extractor
def extract_fallback_text(page_source):
    soup = BeautifulSoup(page_source, "html.parser")
    texts = []

    # Look for text in common review containers
    containers = soup.find_all(["div", "section", "article"], class_=re.compile(r'review|testimonial|feedback|comment'))

    for container in containers:
        text = container.get_text(strip=True)
        if is_review_text(text):
            texts.append(text)

    # If no structured reviews found, look for substantial text blocks
    if not texts:
        for tag in soup.find_all(["p", "div", "span"]):
            text = tag.get_text(strip=True)
            if is_review_text(text):
                texts.append(text)

    return list(set(texts))  # Remove duplicates


def extract_page_text_snippets(url, max_items=20):
    """Extract readable page snippets when no reviews are available."""
    normalized = _normalize_url(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(normalized, headers=headers, timeout=10)
    except Exception:
        return []

    if not resp.ok or not resp.text:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    candidates = []
    seen = set()

    for tag in soup.find_all(["p", "li", "blockquote"]):
        text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
        if not text:
            continue
        if len(text) < 60 or len(text) > 280:
            continue
        lowered = text.lower()
        if _looks_like_navigation_noise(lowered):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(text)
        if len(candidates) >= max_items:
            break

    if not candidates:
        description = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            description = meta.get("content").strip()
        if description and len(description) >= 60:
            candidates.append(description)

    return candidates[:max_items]


def scrape_reviews(url, max_reviews=100):
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless")  # Run in headless mode for server environments
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        started_at = time.time()
        budget = _scrape_time_budget_seconds()
        service = webdriver.ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        time.sleep(5)  # Wait for page to load

        reviews = set()

        # 🔹 STEP 1: Extract JSON-LD structured reviews
        print("Extracting JSON-LD reviews...")
        jsonld_reviews = extract_jsonld_reviews(driver.page_source)
        for r in jsonld_reviews:
            reviews.add(r)
        print(f"Found {len(jsonld_reviews)} JSON-LD reviews")

        # 🔹 STEP 2: Extract platform-specific reviews
        print("Extracting platform-specific reviews...")
        platform_reviews = extract_platform_reviews(driver, url)
        for r in platform_reviews:
            reviews.add(r)
        print(f"Found {len(platform_reviews)} platform reviews")

        # 🔹 STEP 3: Extract structured reviews using CSS selectors
        print("Extracting structured reviews...")
        structured_reviews = extract_structured_reviews(driver)
        for r in structured_reviews:
            reviews.add(r)
        print(f"Found {len(structured_reviews)} structured reviews")

        # 🔹 STEP 4: If still need more reviews, scroll and search
        if len(reviews) < max_reviews and (time.time() - started_at) < budget:
            print("Scrolling for more reviews...")
            scrolls = 0
            last_review_count = len(reviews)

            while len(reviews) < max_reviews and scrolls < 5:  # Limit to 5 scrolls max
                # Scroll down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(WAIT_TIME)

                # Try to click "load more" buttons
                try:
                    load_more_buttons = driver.find_elements(By.XPATH,
                        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]")
                    for button in load_more_buttons:
                        try:
                            if button.is_displayed():
                                button.click()
                                time.sleep(1)
                                break
                        except:
                            pass
                except:
                    pass

                # Extract reviews from newly loaded content
                try:
                    new_reviews = extract_structured_reviews(driver)
                    new_count = 0
                    for r in new_reviews:
                        if r not in reviews:
                            reviews.add(r)
                            new_count += 1

                    # If no new reviews found in this scroll, might be done
                    if new_count == 0:
                        break

                except Exception as e:
                    print(f"Error during scroll extraction: {e}")
                    break

                scrolls += 1
                if scrolls % 2 == 0:
                    print(f"After {scrolls} scrolls: {len(reviews)} reviews found")

        # 🔹 STEP 4B: Discover and crawl internal review pages when initial URL isn't review-heavy.
        if len(reviews) < max_reviews and (time.time() - started_at) < budget:
            candidate_links = _extract_candidate_review_links(url, driver.page_source, limit=4)
            if candidate_links:
                print(f"Crawling candidate review links: {len(candidate_links)}")
            for link in candidate_links:
                if (time.time() - started_at) >= budget or len(reviews) >= max_reviews:
                    break
                try:
                    driver.get(link)
                    time.sleep(2)

                    link_jsonld = extract_jsonld_reviews(driver.page_source)
                    for r in link_jsonld:
                        reviews.add(r)

                    link_structured = extract_structured_reviews(driver)
                    for r in link_structured:
                        reviews.add(r)
                except Exception as link_exc:
                    print(f"Review-link crawl error for {link}: {link_exc}")
                    continue

        # 🔹 STEP 5: Traverse next review pages (page 2/3/...) when available.
        if len(reviews) < max_reviews and (time.time() - started_at) < budget:
            page_hops = 0
            while page_hops < 3 and len(reviews) < max_reviews:
                if (time.time() - started_at) >= budget:
                    break

                moved_next = _go_to_next_review_page(driver)
                if not moved_next:
                    break

                page_hops += 1

                try:
                    next_jsonld = extract_jsonld_reviews(driver.page_source)
                    for r in next_jsonld:
                        reviews.add(r)
                except Exception:
                    pass

                try:
                    next_platform_reviews = extract_platform_reviews(driver, driver.current_url)
                    for r in next_platform_reviews:
                        reviews.add(r)
                except Exception:
                    pass

                try:
                    next_structured = extract_structured_reviews(driver)
                    for r in next_structured:
                        reviews.add(r)
                except Exception:
                    pass

        # 🔹 STEP 6: FALLBACK EXTRACTION (if still no reviews)
        if not reviews and (time.time() - started_at) < budget:
            print("Using fallback extraction...")
            fallback_texts = extract_fallback_text(driver.page_source)
            for txt in fallback_texts:
                reviews.add(txt)
            print(f"Found {len(fallback_texts)} fallback reviews")

        driver.quit()

        # 🔹 FINAL SAFETY: Clean and filter reviews
        filtered_reviews = []
        for review in reviews:
            review = review.strip()
            if len(review) > 20 and len(review.split()) > 3:
                # Remove duplicates and very similar reviews
                is_duplicate = False
                for existing in filtered_reviews:
                    if review.lower() in existing.lower() or existing.lower() in review.lower():
                        if abs(len(review) - len(existing)) < 50:  # Similar length
                            is_duplicate = True
                            break
                if not is_duplicate:
                    filtered_reviews.append(review)

        if not filtered_reviews:
            return []

        print(f"Total unique reviews extracted: {len(filtered_reviews)}")
        return filtered_reviews[:max_reviews]

    except Exception as e:
        print(f"Error in scrape_reviews: {e}")
        return []


def _normalize_url(url):
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def _extract_business_query(url):
    """Build a best-effort Google Maps search query from website metadata."""
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    domain = parsed.netloc.lower().replace("www.", "")
    base_name = (domain.split(".")[0] if domain else "").replace("-", " ").replace("_", " ").strip()

    candidates = []

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(normalized, headers=headers, timeout=8)
        if resp.ok and resp.text:
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else ""
            og_site_name = ""
            og_tag = soup.find("meta", attrs={"property": "og:site_name"})
            if og_tag and og_tag.get("content"):
                og_site_name = og_tag.get("content").strip()

            app_name = ""
            app_tag = soup.find("meta", attrs={"name": "application-name"})
            if app_tag and app_tag.get("content"):
                app_name = app_tag.get("content").strip()

            candidates.extend([og_site_name, app_name, title])
    except Exception as e:
        print(f"Metadata extraction error: {e}")

    if base_name:
        candidates.append(base_name)

    cleaned = []
    for item in candidates:
        if not item:
            continue
        name = re.sub(r"\s+", " ", item).strip()
        if not name:
            continue
        # Trim common title suffixes.
        name = re.sub(r"\s*\|\s*.*$", "", name)
        name = re.sub(r"\s*-\s*.*$", "", name)
        if 2 <= len(name) <= 120:
            cleaned.append(name)

    primary = cleaned[0] if cleaned else base_name or domain or "business"
    return f"{primary} {domain} reviews".strip()


def _build_chrome_driver():
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = webdriver.ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(20)
    driver.set_script_timeout(20)
    return driver


def _click_if_present(driver, xpaths, wait=1.5):
    for xpath in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for element in elements:
                if element.is_displayed():
                    element.click()
                    time.sleep(wait)
                    return True
        except Exception:
            continue
    return False


def _go_to_next_review_page(driver):
    """Try common next-page controls used on review listings."""
    selectors = [
        "//a[@rel='next']",
        "//a[contains(@aria-label, 'Next')]",
        "//button[contains(@aria-label, 'Next')]",
        "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
        "//li[contains(@class,'a-last') and not(contains(@class,'a-disabled'))]/a",  # Amazon
        "//a[contains(@class, '_9QVEpD') and contains(., 'Next')]",                    # Flipkart
        "//a[contains(@class, 'next') and not(contains(@class, 'disabled'))]",
        "//button[contains(@class, 'next') and not(@disabled)]",
    ]

    for selector in selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            for element in elements:
                try:
                    if not element.is_displayed() or not element.is_enabled():
                        continue
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
                    time.sleep(0.7)
                    element.click()
                    time.sleep(2)
                    return True
                except Exception:
                    continue
        except Exception:
            continue

    return False


def _is_google_maps_url(url):
    lowered = (url or "").lower()
    return ("google.com/maps" in lowered) or ("goo.gl/maps" in lowered)


def _google_places_reviews_from_api(url, max_reviews=100):
    """Read original Google reviews via official Places API when API key is configured."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if (not api_key) or (api_key.upper() in {"YOUR_API_KEY", "YOUR-API-KEY", "PLACEHOLDER"}):
        return {
            "reviews": [],
            "provider": "google_places_api",
            "used": False,
            "reason": "invalid_or_missing_api_key",
            "place_name": "",
            "place_url": ""
        }

    query = _extract_business_query(url)
    try:
        text_search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        text_search_params = {
            "query": query,
            "key": api_key
        }
        text_resp = requests.get(text_search_url, params=text_search_params, timeout=12)
        text_data = text_resp.json() if text_resp.ok else {}
        candidates = text_data.get("results", []) if isinstance(text_data, dict) else []

        if not candidates:
            return {
                "reviews": [],
                "provider": "google_places_api",
                "used": True,
                "reason": "no_place_found",
                "place_name": "",
                "place_url": ""
            }

        place_id = candidates[0].get("place_id", "")
        if not place_id:
            return {
                "reviews": [],
                "provider": "google_places_api",
                "used": True,
                "reason": "missing_place_id",
                "place_name": "",
                "place_url": ""
            }

        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "name,url,website,reviews",
            "reviews_sort": "newest",
            "key": api_key
        }
        details_resp = requests.get(details_url, params=details_params, timeout=12)
        details_data = details_resp.json() if details_resp.ok else {}
        result = details_data.get("result", {}) if isinstance(details_data, dict) else {}

        place_name = result.get("name", "")
        place_url = result.get("url", "")
        raw_reviews = result.get("reviews", [])

        cleaned_reviews = []
        for item in raw_reviews:
            text = re.sub(r"\s+", " ", item.get("text", "")).strip()
            if text and len(text) >= 20:
                cleaned_reviews.append(text)

        return {
            "reviews": cleaned_reviews[:max_reviews],
            "provider": "google_places_api",
            "used": True,
            "reason": "ok",
            "place_name": place_name,
            "place_url": place_url
        }

    except Exception as e:
        print(f"Google Places API error: {e}")
        return {
            "reviews": [],
            "provider": "google_places_api",
            "used": True,
            "reason": "api_error",
            "place_name": "",
            "place_url": ""
        }


def scrape_google_reviews(url, max_reviews=100, use_api=True):
    # Prefer official Places API for original Google reviews when configured.
    if use_api:
        api_result = _google_places_reviews_from_api(url, max_reviews)
        if api_result["reviews"]:
            print("Using Google Places API reviews.")
            return api_result["reviews"]

    normalized_url = _normalize_url(url)
    direct_maps = _is_google_maps_url(normalized_url)
    if direct_maps:
        query = "direct_google_maps_url"
        maps_url = normalized_url
    else:
        query = _extract_business_query(normalized_url)
        maps_url = f"https://www.google.com/maps/search/{quote_plus(query)}"

    driver = None
    try:
        started_at = time.time()
        budget = _scrape_time_budget_seconds()
        print(f"Searching Google Maps with query: {query}")
        driver = _build_chrome_driver()
        driver.get(maps_url)
        time.sleep(4)

        # Cookie/consent dialogs (region dependent).
        _click_if_present(driver, [
            "//button[contains(., 'Accept all')]",
            "//button[contains(., 'I agree')]",
            "//button[contains(., 'Accept')]"
        ])

        # Open first place result if needed for search pages.
        if not direct_maps:
            _click_if_present(driver, [
                "(//a[contains(@href, '/maps/place')])[1]",
                "(//div[@role='article']//a)[1]"
            ])

        # Open review panel.
        opened_reviews = _click_if_present(driver, [
            "//button[contains(@aria-label, 'reviews')]",
            "//button[contains(., 'reviews')]",
            "//button[contains(., 'Reviews')]"
        ], wait=2)

        if not opened_reviews:
            print("Could not open Google review panel.")

        reviews = set()
        same_count_rounds = 0
        last_count = 0

        for _ in range(18):
            if (time.time() - started_at) > budget:
                print("Google scrape time budget exceeded.")
                break

            review_elements = []
            selectors = [
                "//span[contains(@class, 'wiI7pd')]",
                "//div[contains(@class, 'MyEned')]//span",
                "//div[@data-review-id]//span[contains(@class, 'wiI7pd')]"
            ]

            for selector in selectors:
                try:
                    review_elements.extend(driver.find_elements(By.XPATH, selector))
                except Exception:
                    continue

            for element in review_elements:
                try:
                    text = element.text.strip()
                    if text and 10 < len(text) < 2000:
                        reviews.add(text)
                except Exception:
                    continue

            if len(reviews) >= max_reviews:
                break

            try:
                # Scroll the review panel first; fallback to page scroll.
                containers = driver.find_elements(By.XPATH, "//div[contains(@class, 'm6QErb') and @aria-label]")
                if containers:
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", containers[0])
                else:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass

            time.sleep(1.8)

            if len(reviews) == last_count:
                same_count_rounds += 1
                if same_count_rounds >= 4:
                    break
            else:
                same_count_rounds = 0
                last_count = len(reviews)

        filtered = []
        for review in reviews:
            compact = re.sub(r"\s+", " ", review).strip()
            if len(compact) >= 20 and compact not in filtered:
                filtered.append(compact)

        print(f"Total Google reviews extracted: {len(filtered)}")
        return filtered[:max_reviews]

    except Exception as e:
        print(f"Error in scrape_google_reviews: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_google_reviews_with_meta(url, max_reviews=100):
    """Return reviews plus extraction method metadata for UI/API visibility."""
    api_result = _google_places_reviews_from_api(url, max_reviews)
    if api_result["reviews"]:
        return {
            "reviews": api_result["reviews"],
            "method": "google_places_api",
            "reason": api_result.get("reason", "ok"),
            "place_name": api_result.get("place_name", ""),
            "place_url": api_result.get("place_url", "")
        }

    # Avoid broad Maps search fallback for arbitrary non-maps URLs to reduce irrelevant/fake matches.
    if not _is_google_maps_url(url):
        return {
            "reviews": [],
            "method": "google_not_found",
            "reason": api_result.get("reason", "google_not_found"),
            "place_name": "",
            "place_url": ""
        }

    scraped_reviews = scrape_google_reviews(url, max_reviews, use_api=False)
    return {
        "reviews": scraped_reviews,
        "method": "google_maps_scraping" if scraped_reviews else "google_not_found",
        "reason": api_result.get("reason", "google_not_found"),
        "place_name": "",
        "place_url": ""
    }


def collect_google_original_review_rows(url, max_reviews=100):
    """Collect original Google reviews (with metadata) for dataset CSV generation."""
    if _is_google_maps_url(url):
        scraped = scrape_google_reviews(url, max_reviews=max_reviews, use_api=False)
        rows = []
        for text in scraped:
            clean = re.sub(r"\s+", " ", (text or "")).strip()
            if not clean:
                continue
            rows.append({
                "platform": "google",
                "source_type": "google_maps_scraping",
                "author": "",
                "rating": "",
                "published_at": "",
                "text": clean,
                "permalink": url,
                "place_name": "",
                "place_url": url,
            })
        return {
            "rows": rows,
            "reason": "direct_maps_scrape" if rows else "direct_maps_no_reviews",
            "place_name": "",
            "place_url": url,
        }

    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if (not api_key) or (api_key.upper() in {"YOUR_API_KEY", "YOUR-API-KEY", "PLACEHOLDER"}):
        return {
            "rows": [],
            "reason": "invalid_or_missing_api_key",
            "place_name": "",
            "place_url": ""
        }

    query = _extract_business_query(url)
    try:
        text_search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        text_resp = requests.get(
            text_search_url,
            params={"query": query, "key": api_key},
            timeout=12,
        )
        text_data = text_resp.json() if text_resp.ok else {}
        candidates = text_data.get("results", []) if isinstance(text_data, dict) else []
        if not candidates:
            return {
                "rows": [],
                "reason": "no_place_found",
                "place_name": "",
                "place_url": ""
            }

        place_id = candidates[0].get("place_id", "")
        if not place_id:
            return {
                "rows": [],
                "reason": "missing_place_id",
                "place_name": "",
                "place_url": ""
            }

        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_resp = requests.get(
            details_url,
            params={
                "place_id": place_id,
                "fields": "name,url,reviews",
                "reviews_sort": "newest",
                "key": api_key,
            },
            timeout=12,
        )
        details_data = details_resp.json() if details_resp.ok else {}
        result = details_data.get("result", {}) if isinstance(details_data, dict) else {}

        place_name = result.get("name", "")
        place_url = result.get("url", "")
        raw_reviews = result.get("reviews", [])

        rows = []
        for item in raw_reviews[:max_reviews]:
            text = re.sub(r"\s+", " ", item.get("text", "")).strip()
            if not text:
                continue
            rows.append({
                "platform": "google",
                "source_type": "google_places_api",
                "author": item.get("author_name", ""),
                "rating": item.get("rating", ""),
                "published_at": item.get("relative_time_description", ""),
                "text": text,
                "permalink": item.get("author_url", ""),
                "place_name": place_name,
                "place_url": place_url,
            })

        return {
            "rows": rows,
            "reason": "ok" if rows else "no_reviews_returned",
            "place_name": place_name,
            "place_url": place_url,
        }

    except Exception as e:
        print(f"collect_google_original_review_rows error: {e}")
        return {
            "rows": [],
            "reason": "api_error",
            "place_name": "",
            "place_url": ""
        }


def _iter_ldjson_nodes(obj):
    """Yield JSON-LD nodes from dict/list payloads, including @graph containers."""
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_ldjson_nodes(item)
        return

    if not isinstance(obj, dict):
        return

    if isinstance(obj.get("@graph"), list):
        for node in obj["@graph"]:
            yield from _iter_ldjson_nodes(node)

    yield obj


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _ldjson_review_to_row(review_obj, base_url):
    if not isinstance(review_obj, dict):
        return None

    text = re.sub(r"\s+", " ", (review_obj.get("reviewBody") or review_obj.get("description") or "")).strip()
    if not text:
        return None

    rating_obj = review_obj.get("reviewRating") if isinstance(review_obj.get("reviewRating"), dict) else {}
    rating = rating_obj.get("ratingValue", "")

    author = ""
    author_obj = review_obj.get("author")
    if isinstance(author_obj, dict):
        author = (author_obj.get("name") or "").strip()
    elif isinstance(author_obj, str):
        author = author_obj.strip()

    published_at = (review_obj.get("datePublished") or "").strip()

    return {
        "platform": "website",
        "source_type": "website_jsonld",
        "author": author,
        "rating": rating,
        "published_at": published_at,
        "text": text,
        "permalink": base_url,
        "place_name": "",
        "place_url": base_url,
    }


def _extract_rating_from_text(text):
    candidate = (text or "").strip()
    if not candidate:
        return ""

    # Examples: 4.5/5, 4 out of 5, 5 stars
    patterns = [
        r"\b([1-5](?:\.\d+)?)\s*/\s*5\b",
        r"\b([1-5](?:\.\d+)?)\s*out\s*of\s*5\b",
        r"\b([1-5](?:\.\d+)?)\s*stars?\b",
    ]
    lowered = candidate.lower()
    for pattern in patterns:
        m = re.search(pattern, lowered)
        if m:
            return m.group(1)
    return ""


def _extract_website_rows_from_soup(soup, base_url, max_reviews=100):
    """Extract review rows with metadata from common HTML review containers."""
    rows = []
    seen = set()

    container_candidates = []

    # Review-like containers by class/id/itemprop.
    for tag_name in ["article", "section", "div", "li"]:
        container_candidates.extend(
            soup.find_all(tag_name, class_=re.compile(r"review|testimonial|feedback|comment", re.I))
        )
        container_candidates.extend(
            soup.find_all(tag_name, id=re.compile(r"review|testimonial|feedback|comment", re.I))
        )

    container_candidates.extend(soup.select("[itemprop='review']"))

    for container in container_candidates:
        try:
            text = re.sub(r"\s+", " ", container.get_text(" ", strip=True)).strip()
            if not text or not is_review_text(text):
                continue

            key = text.lower()
            if key in seen:
                continue

            author = ""
            date_text = ""
            rating = ""

            # Author hints.
            author_nodes = container.select(
                "[itemprop='author'], [class*='author'], [class*='reviewer'], [class*='user'], [class*='profile-name'], [class*='name']"
            )
            for node in author_nodes:
                candidate = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
                if 2 <= len(candidate) <= 60 and not any(k in candidate.lower() for k in ["review", "rating", "star", "date"]):
                    author = candidate
                    break

            # Date hints.
            time_node = container.find("time")
            if time_node:
                date_text = (time_node.get("datetime") or time_node.get_text(" ", strip=True) or "").strip()
            if not date_text:
                date_nodes = container.select("[class*='date'], [class*='time'], [class*='publish']")
                for node in date_nodes:
                    candidate = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
                    if 3 <= len(candidate) <= 50:
                        date_text = candidate
                        break

            # Rating hints from attributes or text.
            rating = (container.get("data-rating") or "").strip()
            if not rating:
                rating_nodes = container.select("[class*='rating'], [class*='star'], [itemprop='reviewRating']")
                for node in rating_nodes:
                    rating = _extract_rating_from_text(node.get_text(" ", strip=True))
                    if rating:
                        break
            if not rating:
                rating = _extract_rating_from_text(text)

            rows.append({
                "platform": "website",
                "source_type": "website_html_structured",
                "author": author,
                "rating": rating,
                "published_at": date_text,
                "text": text,
                "permalink": base_url,
                "place_name": "",
                "place_url": base_url,
            })
            seen.add(key)

            if len(rows) >= max_reviews:
                break
        except Exception:
            continue

    return rows[:max_reviews]


def _first_selenium_text(element, selectors):
    for selector in selectors:
        try:
            nodes = element.find_elements(By.XPATH, selector)
            for node in nodes:
                candidate = re.sub(r"\s+", " ", (node.text or "")).strip()
                if candidate:
                    return candidate
        except Exception:
            continue
    return ""


def _extract_website_rows_from_driver(url, max_reviews=100):
    """Extract metadata-rich review rows from dynamic websites using Selenium."""
    rows = []
    seen = set()
    driver = None

    try:
        driver = _build_chrome_driver()
        driver.get(url)
        time.sleep(4)

        # Try loading more review content on dynamic pages.
        for _ in range(3):
            try:
                load_buttons = driver.find_elements(By.XPATH,
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more') or contains(., 'More')]"
                )
                for btn in load_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        time.sleep(0.5)
                        btn.click()
                        time.sleep(1.2)
                        break
            except Exception:
                pass

            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass
            time.sleep(1.0)

        container_selectors = [
            "//div[@data-review-id]",
            "//div[contains(@data-hook, 'review')]",
            "//article[contains(@class, 'review')]",
            "//li[contains(@class, 'review')]",
            "//div[contains(@class, 'review') and string-length(normalize-space(.)) > 40]",
            "//section[contains(@class, 'review') and string-length(normalize-space(.)) > 40]",
        ]

        containers = []
        for selector in container_selectors:
            try:
                containers.extend(driver.find_elements(By.XPATH, selector))
            except Exception:
                continue

        for container in containers:
            try:
                full_text = re.sub(r"\s+", " ", (container.text or "")).strip()
                if not full_text or not is_review_text(full_text):
                    continue

                key = full_text.lower()
                if key in seen:
                    continue

                author = _first_selenium_text(container, [
                    ".//*[@itemprop='author']",
                    ".//*[contains(@class, 'author')]",
                    ".//*[contains(@class, 'reviewer')]",
                    ".//*[contains(@class, 'profile') and contains(@class, 'name')]",
                    ".//*[contains(@class, 'user') and contains(@class, 'name')]",
                ])

                published_at = _first_selenium_text(container, [
                    ".//time",
                    ".//*[contains(@class, 'date')]",
                    ".//*[contains(@class, 'time')]",
                    ".//*[contains(@class, 'publish')]",
                    ".//*[contains(@class, 'created')]",
                ])

                rating = (container.get_attribute("data-rating") or "").strip()
                if not rating:
                    rating_nodes = []
                    for rating_selector in [
                        ".//*[@itemprop='reviewRating']",
                        ".//*[contains(@class, 'rating')]",
                        ".//*[contains(@class, 'star')]",
                        ".//*[contains(@aria-label, 'star')]",
                        ".//*[contains(@aria-label, 'out of 5')]",
                    ]:
                        try:
                            rating_nodes.extend(container.find_elements(By.XPATH, rating_selector))
                        except Exception:
                            continue

                    for node in rating_nodes:
                        candidate = (node.get_attribute("aria-label") or node.text or "").strip()
                        rating = _extract_rating_from_text(candidate)
                        if rating:
                            break

                if not rating:
                    rating = _extract_rating_from_text(full_text)

                rows.append({
                    "platform": "website",
                    "source_type": "website_selenium_structured",
                    "author": author,
                    "rating": rating,
                    "published_at": published_at,
                    "text": full_text,
                    "permalink": url,
                    "place_name": "",
                    "place_url": url,
                })
                seen.add(key)

                if len(rows) >= max_reviews:
                    break
            except Exception:
                continue
    except Exception as exc:
        print(f"_extract_website_rows_from_driver error: {exc}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return rows[:max_reviews]


def collect_website_original_review_rows(url, max_reviews=100):
    """Collect original review rows from website URL using JSON-LD plus scraping merge."""
    normalized = _normalize_url(url)
    max_reviews = max(1, min(int(max_reviews or 100), 300))
    min_target_before_skip_scrape = min(max_reviews, 12)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    rows = []
    seen = set()
    jsonld_count = 0
    html_structured_count = 0
    selenium_structured_count = 0

    try:
        resp = requests.get(normalized, headers=headers, timeout=12)
        if resp.ok and resp.text:
            soup = BeautifulSoup(resp.text, "html.parser")
            scripts = soup.find_all("script", type="application/ld+json")

            for script in scripts:
                raw_json = script.string or script.get_text() or ""
                raw_json = raw_json.strip()
                if not raw_json:
                    continue

                try:
                    payload = json.loads(raw_json)
                except Exception:
                    continue

                for node in _iter_ldjson_nodes(payload):
                    node_type = str(node.get("@type", "")).lower()
                    if node_type == "review":
                        row = _ldjson_review_to_row(node, normalized)
                        if row and row["text"].lower() not in seen:
                            seen.add(row["text"].lower())
                            rows.append(row)

                    for review_obj in _as_list(node.get("review")):
                        row = _ldjson_review_to_row(review_obj, normalized)
                        if row and row["text"].lower() not in seen:
                            seen.add(row["text"].lower())
                            rows.append(row)

                    if len(rows) >= max_reviews:
                        break

                if len(rows) >= max_reviews:
                    break

            if len(rows) < max_reviews:
                structured_rows = _extract_website_rows_from_soup(
                    soup=soup,
                    base_url=normalized,
                    max_reviews=max_reviews,
                )
                for row in structured_rows:
                    key = (row.get("text") or "").lower().strip()
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    rows.append(row)
                    html_structured_count += 1
                    if len(rows) >= max_reviews:
                        break

        jsonld_count = len(rows)
    except Exception as e:
        print(f"collect_website_original_review_rows jsonld error: {e}")

    # If JSON-LD yielded only a few rows, continue with scraping and merge both sources.
    scraped_count = 0
    if len(rows) < min_target_before_skip_scrape:
        try:
            selenium_rows = _extract_website_rows_from_driver(normalized, max_reviews=max_reviews)
            for row in selenium_rows:
                key = (row.get("text") or "").lower().strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                rows.append(row)
                selenium_structured_count += 1
                if len(rows) >= max_reviews:
                    break
        except Exception as e:
            print(f"collect_website_original_review_rows selenium metadata error: {e}")

    if len(rows) < min_target_before_skip_scrape:
        try:
            scraped = scrape_reviews(normalized, max_reviews=max_reviews)
            for text in scraped:
                clean = re.sub(r"\s+", " ", (text or "")).strip()
                if not clean:
                    continue
                key = clean.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "platform": "website",
                    "source_type": "website_scraping",
                    "author": "",
                    "rating": "",
                    "published_at": "",
                    "text": clean,
                    "permalink": normalized,
                    "place_name": "",
                    "place_url": normalized,
                })
                scraped_count += 1
                if len(rows) >= max_reviews:
                    break
        except Exception as e:
            print(f"collect_website_original_review_rows scrape error: {e}")

    final_rows = rows[:max_reviews]
    if not final_rows:
        return {
            "rows": [],
            "reason": "website_no_reviews",
        }

    if jsonld_count > 0 and (html_structured_count > 0 or selenium_structured_count > 0 or scraped_count > 0):
        reason = "website_jsonld_plus_scraping"
    elif html_structured_count > 0 and selenium_structured_count > 0:
        reason = "website_html_plus_selenium_structured"
    elif selenium_structured_count > 0 and scraped_count > 0:
        reason = "website_selenium_structured_plus_scraping"
    elif html_structured_count > 0 and scraped_count > 0:
        reason = "website_html_structured_plus_scraping"
    elif jsonld_count > 0:
        reason = "website_jsonld"
    elif selenium_structured_count > 0:
        reason = "website_selenium_structured"
    elif html_structured_count > 0:
        reason = "website_html_structured"
    else:
        reason = "website_scraping"

    return {
        "rows": final_rows,
        "reason": reason,
    }


def collect_reddit_social_rows(url, max_items=50):
    """Collect social mentions from Reddit public search endpoint."""
    try:
        normalized = _normalize_url(url)
        parsed = urlparse(normalized)
        domain = parsed.netloc.lower().replace("www.", "")
        base_term = domain.split(".")[0] if domain else ""
        query = f'("{base_term}" OR "{domain}") review'

        headers = {
            "User-Agent": "sentilytics/1.0 (review dataset collector)"
        }
        resp = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "new", "limit": min(max_items, 100)},
            headers=headers,
            timeout=12,
        )

        if not resp.ok:
            return []

        payload = resp.json()
        children = payload.get("data", {}).get("children", [])
        rows = []
        for child in children:
            post = child.get("data", {})
            title = (post.get("title") or "").strip()
            body = (post.get("selftext") or "").strip()
            text = f"{title}. {body}".strip(". ")
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) < 20:
                continue

            created_utc = post.get("created_utc")
            published_at = ""
            if created_utc:
                try:
                    published_at = datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat()
                except Exception:
                    published_at = ""

            rows.append({
                "platform": "reddit",
                "source_type": "social_media",
                "author": post.get("author", ""),
                "rating": "",
                "published_at": published_at,
                "text": text,
                "permalink": f"https://www.reddit.com{post.get('permalink', '')}",
                "place_name": "",
                "place_url": "",
            })

            if len(rows) >= max_items:
                break

        return rows
    except Exception as e:
        print(f"collect_reddit_social_rows error: {e}")
        return []


def collect_facebook_comment_rows(max_items=50):
    """Collect official Facebook comments via Graph API using FB_POST_ID + FB_GRAPH_ACCESS_TOKEN."""
    access_token = os.getenv("FB_GRAPH_ACCESS_TOKEN", "").strip()
    post_id = os.getenv("FB_POST_ID", "").strip()
    if not access_token or not post_id:
        return []

    try:
        resp = requests.get(
            f"https://graph.facebook.com/v20.0/{post_id}/comments",
            params={
                "fields": "from{id,name},message,created_time,permalink_url",
                "limit": min(max_items, 100),
                "access_token": access_token,
            },
            timeout=12,
        )
        if not resp.ok:
            return []

        payload = resp.json()
        rows = []
        for item in payload.get("data", []):
            text = re.sub(r"\s+", " ", (item.get("message") or "")).strip()
            if len(text) < 15:
                continue
            author = (item.get("from") or {}).get("name", "")
            rows.append({
                "platform": "facebook",
                "source_type": "social_media_graph_api",
                "author": author,
                "rating": "",
                "published_at": item.get("created_time", ""),
                "text": text,
                "permalink": item.get("permalink_url", ""),
                "place_name": "",
                "place_url": "",
            })
            if len(rows) >= max_items:
                break
        return rows
    except Exception as e:
        print(f"collect_facebook_comment_rows error: {e}")
        return []


def collect_instagram_comment_rows(max_items=50):
    """Collect official Instagram comments via Graph API using IG_MEDIA_ID + FB_GRAPH_ACCESS_TOKEN."""
    access_token = os.getenv("FB_GRAPH_ACCESS_TOKEN", "").strip()
    media_id = os.getenv("IG_MEDIA_ID", "").strip()
    if not access_token or not media_id:
        return []

    try:
        resp = requests.get(
            f"https://graph.facebook.com/v20.0/{media_id}/comments",
            params={
                "fields": "username,text,timestamp,id",
                "limit": min(max_items, 100),
                "access_token": access_token,
            },
            timeout=12,
        )
        if not resp.ok:
            return []

        payload = resp.json()
        rows = []
        for item in payload.get("data", []):
            text = re.sub(r"\s+", " ", (item.get("text") or "")).strip()
            if len(text) < 15:
                continue
            comment_id = item.get("id", "")
            permalink = f"https://www.instagram.com/p/{media_id}/" if comment_id else ""
            rows.append({
                "platform": "instagram",
                "source_type": "social_media_graph_api",
                "author": item.get("username", ""),
                "rating": "",
                "published_at": item.get("timestamp", ""),
                "text": text,
                "permalink": permalink,
                "place_name": "",
                "place_url": "",
            })
            if len(rows) >= max_items:
                break
        return rows
    except Exception as e:
        print(f"collect_instagram_comment_rows error: {e}")
        return []
