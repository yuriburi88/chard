import os
import json
import yaml
from datetime import datetime, timedelta, timezone
import glob
from urllib.parse import urlparse

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.yml")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TARGET_DATE = datetime(2025, 12, 10, 14, 36, 12, tzinfo=timezone(timedelta(hours=9)))
WINDOW_HOURS = 24

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_feed_map(config):
    feed_map = {}
    for source in config.get("rss_sources", []):
        url = source.get("url")
        name = source.get("name")
        if url and name:
            domain = urlparse(url).netloc.replace("www.", "")
            feed_map[domain] = name
    return feed_map

def get_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except:
        return ""

def main():
    print(f"Verifying RSS data collection for the last {WINDOW_HOURS} hours from {TARGET_DATE}")
    
    config = load_config()
    feed_map = get_feed_map(config)
    
    # Calculate window start
    window_start = TARGET_DATE - timedelta(hours=WINDOW_HOURS)
    print(f"Window Start (KST): {window_start}")
    
    # Find relevant files (yesterday and today)
    dates_to_check = [
        window_start.strftime("%Y-%m-%d"),
        TARGET_DATE.strftime("%Y-%m-%d")
    ]
    
    files = []
    for d in set(dates_to_check):
        path = os.path.join(OUTPUT_DIR, d, "collected_*_raw.json")
        files.extend(glob.glob(path))
    
    print(f"Found {len(files)} raw data files to analyze.")
    
    stats = {name: set() for name in feed_map.values()}
    unknown_sources = set()
    total_rss_items = 0
    in_window_rss_items = 0
    
    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for item in data:
                if item.get("source") != "rss":
                    continue
                
                total_rss_items += 1
                
                # Check timestamp
                ts_str = item.get("timestamp")
                if not ts_str:
                    continue
                
                # Parse timestamp (handle various formats if needed, but assuming isoformat)
                try:
                    # Python 3.11+ handle fromisoformat with 'Z' usually, but safe to replace
                    if ts_str.endswith('Z'):
                        ts_str = ts_str[:-1] + '+00:00'
                    item_dt = datetime.fromisoformat(ts_str)
                    
                    # Ensure timezone awareness (timestamps in file seem to be +00:00)
                    if item_dt.tzinfo is None:
                         item_dt = item_dt.replace(tzinfo=timezone.utc)
                    
                    # Convert to KST for comparison or just compare aware datetimes
                    # item_dt is mostly UTC based on sample
                    
                except ValueError as e:
                    # Attempt simple fallback or skip
                    continue
                
                if item_dt > window_start and item_dt <= TARGET_DATE:
                    in_window_rss_items += 1
                    url = item.get("meta", {}).get("url")
                    if not url:
                        continue
                        
                    domain = get_domain(url)
                    feed_name = None
                    
                    # Try exact match first
                    if domain in feed_map:
                        feed_name = feed_map[domain]
                    else:
                        # Try partial match
                        for k, v in feed_map.items():
                            if k in domain or domain in k:
                                feed_name = v
                                break
                    
                    if feed_name:
                        stats[feed_name].add(url)
                    else:
                        # Track unknown domains
                        unknown_sources.add(domain)
                        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print("-" * 50)
    print(f"Total RSS Items Scanned: {total_rss_items}")
    print(f"RSS Items in Last 24h: {in_window_rss_items}")
    print("-" * 50)
    print("Unique Articles Collected per Feed (Last 24h):")
    print("-" * 50)
    
    for name, urls in sorted(stats.items()):
        print(f"{name}: {len(urls)}")
        
    if unknown_sources:
        print("-" * 50)
        print("Unknown Sources (Unmapped Domains):")
        for s in unknown_sources:
            print(f"- {s}")

if __name__ == "__main__":
    main()
