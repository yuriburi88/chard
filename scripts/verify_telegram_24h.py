import os
import json
import yaml
from datetime import datetime, timedelta, timezone
import glob

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TARGET_DATE = datetime(2025, 12, 10, 15, 5, 36, tzinfo=timezone(timedelta(hours=9)))
WINDOW_HOURS = 24

def main():
    print(f"Verifying Telegram collection for the last {WINDOW_HOURS} hours from {TARGET_DATE}")
    
    # Calculate window start
    window_start = TARGET_DATE - timedelta(hours=WINDOW_HOURS)
    print(f"Window Start (KST): {window_start}")
    
    # Find relevant files
    dates_to_check = [
        window_start.strftime("%Y-%m-%d"),
        TARGET_DATE.strftime("%Y-%m-%d")
    ]
    
    files = []
    for d in set(dates_to_check):
        path = os.path.join(OUTPUT_DIR, d, "collected_*_raw.json")
        files.extend(glob.glob(path))
        
    print(f"Found {len(files)} raw data files to analyze.")
    
    stats = {} # channel_name -> count
    stats_by_id = {} # channel_id (from meta) -> count
    total_tg_items = 0
    in_window_tg_items = 0
    
    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for item in data:
                if item.get("source") != "telegram":
                    continue
                
                total_tg_items += 1
                
                ts_str = item.get("timestamp")
                if not ts_str:
                    continue
                    
                try:
                    if ts_str.endswith('Z'):
                        ts_str = ts_str[:-1] + '+00:00'
                    item_dt = datetime.fromisoformat(ts_str)
                    if item_dt.tzinfo is None:
                         item_dt = item_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                
                if item_dt > window_start and item_dt <= TARGET_DATE:
                    in_window_tg_items += 1
                    meta = item.get("meta", {})
                    
                    # Try to get a readable name
                    channel_name = meta.get("channel_name") or meta.get("channel") or "Unknown"
                    channel_id = meta.get("channel_id", "Unknown ID")
                    
                    stats[channel_name] = stats.get(channel_name, 0) + 1
                    stats_by_id[channel_id] = stats_by_id.get(channel_id, 0) + 1
                        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print("-" * 50)
    print(f"Total Telegram Items Scanned: {total_tg_items}")
    print(f"Telegram Items in Last 24h: {in_window_tg_items}")
    print("-" * 50)
    print("Messages Collected per Channel (Last 24h):")
    print("-" * 50)
    
    for name, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"{name}: {count}")
        
    print("-" * 50)
    print("Breakdown by Channel ID (Meta):")
    for ch_id, count in sorted(stats_by_id.items(), key=lambda x: x[1], reverse=True):
        print(f"ID {ch_id}: {count}")

if __name__ == "__main__":
    main()
