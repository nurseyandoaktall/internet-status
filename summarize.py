import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ---------- CONFIGURATION ----------
BASE_DIR = Path.home() / "internet-status"
LOG_FILE = BASE_DIR / "status.log"
SUMMARY_FILE = BASE_DIR / "summary.json"
UTC_OFFSET = 8  # Display timezone offset (China Standard Time)

def utc_to_local(dt_utc):
    return dt_utc + timedelta(hours=UTC_OFFSET)

def slot_key(local_dt):
    """Return a 15-minute slot key: YYYY-MM-DDTHH:MM in local time"""
    minute = (local_dt.minute // 15) * 15
    return local_dt.strftime(f"%Y-%m-%dT%H:") + f"{minute:02d}"

def parse_log():
    slots = {}  # key -> {online, total, rt_sum, rt_count}

    line_re = re.compile(
        r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2})\s+'
        r'(ONLINE|OFFLINE)\s+'
        r'\[([^\]]+)\]'
        r'(?:\s+\[([^\]]+)\])?'
    )

    with open(LOG_FILE, 'rb') as f:
        for raw in f:
            try:
                line = raw.decode('utf-8', errors='ignore').strip()
            except Exception:
                continue
            if not line:
                continue

            m = line_re.match(line)
            if not m:
                continue

            ts_str, state, status_block, rt_block = m.groups()

            # Parse timestamp
            try:
                # Handle both +00:00 and -05:00 style offsets
                ts_utc = datetime.fromisoformat(ts_str)
                # Convert to UTC then to local
                ts_utc_naive = ts_utc.astimezone(timezone.utc).replace(tzinfo=None)
                local_dt = utc_to_local(datetime.replace(ts_utc_naive, tzinfo=None))
            except Exception:
                continue

            key = slot_key(local_dt)

            if key not in slots:
                slots[key] = {'online': 0, 'total': 0, 'rt_sum': 0.0, 'rt_count': 0}

            slots[key]['total'] += 1
            if state == 'ONLINE':
                slots[key]['online'] += 1

            # Parse response times if present
            if rt_block:
                for part in rt_block.split():
                    if ':' in part:
                        val = part.split(':', 1)[1]
                        if val != 'timeout':
                            try:
                                slots[key]['rt_sum'] += float(val)
                                slots[key]['rt_count'] += 1
                            except ValueError:
                                pass

    return slots

def main():
    print(f"Reading {LOG_FILE}...")
    slots = parse_log()
    print(f"Parsed {len(slots)} slots")

    # Build sorted list
    records = []
    for key in sorted(slots.keys()):
        s = slots[key]
        avg_rt = round(s['rt_sum'] / s['rt_count'], 3) if s['rt_count'] > 0 else None
        records.append({
            't': key,           # local time slot
            'on': s['online'],  # online count
            'n': s['total'],    # total count
            'rt': avg_rt        # avg response time (null if no data)
        })

# Keep only the last 30 days
    if records:
        cutoff = records[-1]['t'][:10]
        cutoff_dt = datetime.strptime(cutoff, '%Y-%m-%d') - timedelta(days=30)
        cutoff_str = cutoff_dt.strftime('%Y-%m-%d')
        records = [r for r in records if r['t'][:10] >= cutoff_str]


    with open(SUMMARY_FILE, 'w') as f:
        json.dump(records, f, separators=(',', ':'))

    size_kb = SUMMARY_FILE.stat().st_size / 1024
    print(f"Written {len(records)} records to {SUMMARY_FILE} ({size_kb:.1f} KB)")

if __name__ == '__main__':
    main()
