import feedparser
import requests
import yaml
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import time

# New RSS feeds to verify
NEW_FEEDS = [
    "https://thedefiant.io/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://cointelegraph.com/rss",
    "https://cryptopotato.com/feed/",
    "https://cryptoslate.com/feed/",
    "https://cryptonews.com/news/feed/",
    "https://smartliquidity.info/feed/",
    "https://finance.yahoo.com/news/rssindex",
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://time.com/nextadvisor/feed/",
    "https://benjaminion.xyz/newineth2/rss_feed.xml"
]

# Load existing config
CONFIG_PATH = "config/config.yml"
def load_existing_feeds():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            existing = {}
            for source in config.get("rss_sources", []):
                url = source.get("url", "")
                name = source.get("name", "")
                existing[url] = name
            return existing
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def get_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except:
        return ""

def verify_feed(url):
    """Verify if RSS feed is valid and get 24h data"""
    result = {
        "url": url,
        "valid": False,
        "accessible": False,
        "has_24h_data": False,
        "article_count": 0,
        "articles_24h": 0,
        "latest_article_date": None,
        "error": None,
        "duplicate": False,
        "existing_name": None,
        "suggested_name": None
    }

    try:
        # Check URL accessibility
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print(f"{'='*60}")

        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            print(f"[FAIL] HTTP Error: {response.status_code}")
            return result

        result["accessible"] = True
        print(f"[OK] Accessible (HTTP {response.status_code})")

        # Parse RSS feed
        feed = feedparser.parse(response.content)

        if not feed.entries:
            result["error"] = "No entries found"
            print(f"[FAIL] No entries found in feed")
            return result

        result["valid"] = True
        result["article_count"] = len(feed.entries)
        print(f"[OK] Valid RSS feed with {len(feed.entries)} entries")

        # Get feed title for suggested name
        feed_title = feed.feed.get("title", get_domain(url))
        result["suggested_name"] = feed_title

        # Check for 24h data
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        articles_24h = 0
        latest_date = None

        for entry in feed.entries:
            # Try to parse date
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

            if pub_date:
                if latest_date is None or pub_date > latest_date:
                    latest_date = pub_date

                if pub_date >= cutoff:
                    articles_24h += 1

        result["articles_24h"] = articles_24h
        result["latest_article_date"] = latest_date
        result["has_24h_data"] = articles_24h > 0

        if latest_date:
            hours_ago = (now - latest_date).total_seconds() / 3600
            print(f"[OK] Latest article: {latest_date.strftime('%Y-%m-%d %H:%M UTC')} ({hours_ago:.1f}h ago)")

        if articles_24h > 0:
            print(f"[OK] Found {articles_24h} articles in last 24 hours")
        else:
            print(f"[WARN] No articles in last 24 hours (latest: {hours_ago:.1f}h ago)")

        time.sleep(1)  # Be nice to servers

    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
        print(f"[FAIL] Timeout error")
    except requests.exceptions.RequestException as e:
        result["error"] = f"Request error: {str(e)[:100]}"
        print(f"[FAIL] Request error: {e}")
    except Exception as e:
        result["error"] = f"Parse error: {str(e)[:100]}"
        print(f"[FAIL] Parse error: {e}")

    return result

def main():
    print("="*80)
    print("RSS FEED VERIFICATION TOOL")
    print("="*80)

    # Load existing feeds
    existing_feeds = load_existing_feeds()
    print(f"\nLoaded {len(existing_feeds)} existing feeds from config.yml")

    # Check for duplicates
    print("\n" + "="*80)
    print("CHECKING FOR DUPLICATES")
    print("="*80)

    duplicates = []
    for url in NEW_FEEDS:
        if url in existing_feeds:
            duplicates.append((url, existing_feeds[url]))
            print(f"[DUPLICATE] {url}")
            print(f"   Already exists as: {existing_feeds[url]}")
        # Also check normalized versions
        elif url.rstrip('/') in existing_feeds:
            duplicates.append((url, existing_feeds[url.rstrip('/')]))
            print(f"[DUPLICATE] {url}")
            print(f"   Already exists as: {existing_feeds[url.rstrip('/')]}")
        elif (url + '/') in existing_feeds:
            duplicates.append((url, existing_feeds[url + '/']))
            print(f"[DUPLICATE] {url}")
            print(f"   Already exists as: {existing_feeds[url + '/']}")

    if not duplicates:
        print("[OK] No duplicates found")

    # Verify all feeds
    print("\n" + "="*80)
    print("VERIFYING RSS FEEDS")
    print("="*80)

    results = []
    for url in NEW_FEEDS:
        result = verify_feed(url)

        # Mark duplicates
        for dup_url, dup_name in duplicates:
            if url == dup_url or url.rstrip('/') == dup_url.rstrip('/'):
                result["duplicate"] = True
                result["existing_name"] = dup_name

        results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    valid_feeds = [r for r in results if r["valid"] and r["has_24h_data"] and not r["duplicate"]]
    duplicate_feeds = [r for r in results if r["duplicate"]]
    invalid_feeds = [r for r in results if not r["valid"] or not r["has_24h_data"]]

    print(f"\n[OK] Valid feeds with 24h data: {len(valid_feeds)}")
    print(f"[DUPLICATE] Duplicate feeds: {len(duplicate_feeds)}")
    print(f"[FAIL] Invalid or no 24h data: {len([r for r in invalid_feeds if not r['duplicate']])}")

    # Duplicates detail
    if duplicate_feeds:
        print("\n" + "-"*80)
        print("DUPLICATE FEEDS (Already in config.yml)")
        print("-"*80)
        for r in duplicate_feeds:
            print(f"\n[DUPLICATE] {r['url']}")
            print(f"   Existing name: {r['existing_name']}")

    # Valid feeds for config.yml
    if valid_feeds:
        print("\n" + "-"*80)
        print("VALID FEEDS - READY TO ADD TO CONFIG.YML")
        print("-"*80)

        for r in valid_feeds:
            print(f"\n[OK] {r['url']}")
            print(f"   Suggested name: {r['suggested_name']}")
            print(f"   Articles (24h): {r['articles_24h']}")
            if r['latest_article_date']:
                print(f"   Latest: {r['latest_article_date'].strftime('%Y-%m-%d %H:%M UTC')}")

        print("\n" + "="*80)
        print("CONFIG.YML FORMAT (Copy & Paste)")
        print("="*80)
        print()

        for r in valid_feeds:
            # Create clean name from suggested name
            name = r['suggested_name'].replace(' ', '').replace('-', '')
            if len(name) > 30:
                name = name[:30]

            # Determine timezone (US sources = -5, others = 0)
            domain = get_domain(r['url'])
            timezone_val = -5 if any(x in domain for x in ['yahoo', 'cnbc', 'time.com']) else 0

            print(f"- name: {name}")
            print(f"  url: {r['url']}")
            print(f"  priority: 1.1")
            print(f"  timezone: {timezone_val}")
            print(f"  max_articles: 5000")
            print(f"  hours_back: 24")

    # Invalid feeds detail
    invalid_non_dup = [r for r in invalid_feeds if not r['duplicate']]
    if invalid_non_dup:
        print("\n" + "-"*80)
        print("INVALID FEEDS OR NO 24H DATA")
        print("-"*80)
        for r in invalid_non_dup:
            print(f"\n[FAIL] {r['url']}")
            if r['error']:
                print(f"   Error: {r['error']}")
            elif r['valid'] and not r['has_24h_data']:
                print(f"   Issue: No articles in last 24 hours")
                if r['latest_article_date']:
                    hours_ago = (datetime.now(timezone.utc) - r['latest_article_date']).total_seconds() / 3600
                    print(f"   Latest article: {hours_ago:.1f}h ago")
            print(f"   Articles found: {r['article_count']}")
            print(f"   Articles (24h): {r['articles_24h']}")

if __name__ == "__main__":
    main()
