import os
import json
import yaml
from datetime import datetime, timedelta, timezone
import glob
from collections import defaultdict

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yml")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
WINDOW_HOURS = 24

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    print("="*80)
    print("TELEGRAM COLLECTION VERIFICATION - DETAILED REPORT")
    print("="*80)

    # Load config
    config = load_config()
    telegram_sources = config.get("telegram_sources", [])

    print(f"\nConfigured Telegram Channels: {len(telegram_sources)}")
    print("-"*80)
    for i, source in enumerate(telegram_sources, 1):
        print(f"{i}. Channel: {source.get('channel_id')}")
        print(f"   Name: {source.get('name')}")
        print(f"   Auth: {source.get('auth_method')}")
        print(f"   Max messages: {source.get('max_messages')}")

    # Calculate window
    now = datetime.now(timezone(timedelta(hours=9)))
    window_start = now - timedelta(hours=WINDOW_HOURS)

    print(f"\n" + "="*80)
    print(f"Checking data from {window_start.strftime('%Y-%m-%d %H:%M KST')} to {now.strftime('%Y-%m-%d %H:%M KST')}")
    print("="*80)

    # Find relevant files
    dates_to_check = [
        window_start.strftime("%Y-%m-%d"),
        now.strftime("%Y-%m-%d")
    ]

    files = []
    for d in set(dates_to_check):
        path = os.path.join(OUTPUT_DIR, d, "collected_*_raw.json")
        found = glob.glob(path)
        files.extend(found)
        if found:
            print(f"[OK] Found {len(found)} files for date {d}")

    if not files:
        print("[FAIL] No data files found!")
        return

    print(f"\n[OK] Total files to analyze: {len(files)}")

    # Statistics
    channel_stats = defaultdict(lambda: {
        'messages': 0,
        'timestamps': [],
        'channel_ids': set(),
        'meta_info': {}
    })

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

                if item_dt > window_start and item_dt <= now:
                    in_window_tg_items += 1
                    meta = item.get("meta", {})

                    # Get channel info
                    channel_name = meta.get("channel_name") or meta.get("channel") or "Unknown"
                    channel_id = meta.get("channel_id", "unknown")

                    channel_stats[channel_name]['messages'] += 1
                    channel_stats[channel_name]['timestamps'].append(item_dt)
                    channel_stats[channel_name]['channel_ids'].add(str(channel_id))

                    # Store first meta info we see
                    if not channel_stats[channel_name]['meta_info']:
                        channel_stats[channel_name]['meta_info'] = meta

        except Exception as e:
            print(f"[FAIL] Error reading {file_path}: {e}")

    print("\n" + "="*80)
    print("COLLECTION SUMMARY")
    print("="*80)

    print(f"\nTotal Telegram messages scanned: {total_tg_items}")
    print(f"Messages in last 24h: {in_window_tg_items}")

    print("\n" + "-"*80)
    print("PER-CHANNEL STATISTICS")
    print("-"*80)

    if not channel_stats:
        print("\n[FAIL] No Telegram messages found in the last 24 hours!")
        print("\nPossible issues:")
        print("1. Telegram channels are not being collected")
        print("2. Session files may be invalid or expired")
        print("3. Channel IDs in config.yml may be incorrect")
        print("4. Authentication may have failed")
    else:
        for channel_name, stats in sorted(channel_stats.items(), key=lambda x: x[1]['messages'], reverse=True):
            print(f"\n[OK] Channel: {channel_name}")
            print(f"     Messages collected: {stats['messages']}")
            print(f"     Channel IDs: {', '.join(stats['channel_ids'])}")

            # Time range
            if stats['timestamps']:
                timestamps = sorted(stats['timestamps'])
                oldest = timestamps[0]
                newest = timestamps[-1]
                kst_oldest = oldest.astimezone(timezone(timedelta(hours=9)))
                kst_newest = newest.astimezone(timezone(timedelta(hours=9)))

                print(f"     Oldest message: {kst_oldest.strftime('%Y-%m-%d %H:%M KST')}")
                print(f"     Newest message: {kst_newest.strftime('%Y-%m-%d %H:%M KST')}")

                # Calculate hourly rate
                time_span = (newest - oldest).total_seconds() / 3600
                if time_span > 0:
                    msg_per_hour = stats['messages'] / time_span
                    print(f"     Message rate: {msg_per_hour:.1f} messages/hour")

    # Check which configured channels are missing
    print("\n" + "="*80)
    print("MISSING CHANNELS CHECK")
    print("="*80)

    collected_channel_ids = set()
    for stats in channel_stats.values():
        collected_channel_ids.update(stats['channel_ids'])

    configured_channel_ids = {source.get('channel_id') for source in telegram_sources}

    missing = configured_channel_ids - collected_channel_ids

    if missing:
        print(f"\n[WARN] {len(missing)} configured channels have NO data in last 24h:")
        for channel_id in missing:
            # Find the config entry
            for source in telegram_sources:
                if source.get('channel_id') == channel_id:
                    print(f"\n  - Channel ID: {channel_id}")
                    print(f"    Name: {source.get('name')}")
                    print(f"    Auth method: {source.get('auth_method')}")
                    print(f"    Session file: {source.get('session_file')}")
                    break

        print("\n[INFO] Possible reasons:")
        print("  1. Channel has no new messages in the last 24 hours")
        print("  2. Authentication/session may have expired")
        print("  3. Channel ID may be incorrect (missing @ or wrong format)")
        print("  4. Bot/account may not have access to the channel")
        print("  5. Collector may have encountered an error")
    else:
        print("\n[OK] All configured channels have collected data!")

    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    if missing:
        print("\n1. Check the main.py execution logs for errors")
        print("2. Verify session files exist and are valid")
        print("3. Test channel access manually")
        print("4. Confirm channel IDs are correct (try with @ prefix if missing)")
    else:
        print("\n[OK] All Telegram sources are working correctly!")

if __name__ == "__main__":
    main()
