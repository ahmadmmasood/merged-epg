import requests
import gzip
import io
from lxml import etree
from datetime import datetime, timedelta
import pytz
import os

# -----------------------
# CONFIG: EPG Sources
# -----------------------
US_PRIMARY = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"
US_LOCALS = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"
US_DIGITAL = "https://www.open-epg.com/files/unitedstates10.xml.gz"

INDIA_FEEDS = [
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz"
]

EGYPT_FEEDS = [
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz"
]

LEBANON_FEEDS = ["https://iptv-epg.org/files/epg-lb.xml.gz"]

ALL_FEEDS = [US_PRIMARY, US_LOCALS, US_DIGITAL] + INDIA_FEEDS + EGYPT_FEEDS + LEBANON_FEEDS

# -----------------------
# CHANNEL KEYWORDS
# -----------------------
US_LOCAL_IDS = ["WRC", "WTTG", "WJLA", "WHUT", "WUSA", "WDCA", "WDCW"]

INDIAN_KEYS = ["balle", "b4u", "9x jalwa", "mtv india", "travel xp"]

EGYPT_MENA_KEYS = ["aghani", "nogoum", "mbc masr", "mbc masr 2", "mbc1"]

# -----------------------
# UTILITY FUNCTIONS
# -----------------------
def is_east_coast(channel_name):
    """Return True if channel is clearly East Coast."""
    name_lower = channel_name.lower()
    return "east" in name_lower and "west" not in name_lower

def channel_matches(channel_name, channel_id):
    """Return True if channel should be included in merged XML."""
    name_lower = channel_name.lower()
    return (
        is_east_coast(channel_name) or                     # East Coast US
        any(loc.lower() in channel_id.lower() for loc in US_LOCAL_IDS) or  # US locals
        any(key in name_lower for key in INDIAN_KEYS) or   # Indian channels
        any(key in name_lower for key in EGYPT_MENA_KEYS) # Egypt/MENA channels
    )

# -----------------------
# MERGE PROCESS
# -----------------------
merged_root = etree.Element("tv")
channels_added = set()
channels_list = []
programs_kept = 0

cutoff = datetime.now(pytz.utc) - timedelta(days=3)

for url in ALL_FEEDS:
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()

    with gzip.open(io.BytesIO(r.content), "rb") as f:
        tree = etree.parse(f)
        root = tree.getroot()

        # Channels
        for ch in root.findall("channel"):
            ch_id = ch.get("id")
            display_names = [d.text for d in ch.findall("display-name") if d.text]
            ch_name = display_names[0] if display_names else ""

            # Avoid duplicates: check id
            if ch_id in channels_added:
                continue

            # Only include if it matches the criteria
            if channel_matches(ch_name, ch_id):
                merged_root.append(ch)
                channels_added.add(ch_id)
                channels_list.append(ch_name)

        # Programs
        for prog in root.findall("programme"):
            ch_id = prog.get("channel")
            if not ch_id or ch_id not in channels_added:
                continue
            start_str = prog.get("start")
            try:
                start_time = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
                start_time = pytz.utc.localize(start_time)
            except Exception:
                continue
            if start_time >= cutoff:
                merged_root.append(prog)
                programs_kept += 1

# -----------------------
# WRITE merged.xml.gz
# -----------------------
tree = etree.ElementTree(merged_root)
with gzip.open("merged.xml.gz", "wb") as f:
    tree.write(f, encoding="UTF-8", xml_declaration=True)

file_size_mb = round(os.path.getsize("merged.xml.gz") / (1024 * 1024), 2)

# -----------------------
# WRITE index.html
# -----------------------
now_local = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")

html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>EPG Merge Status</title></head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {now_local}</p>
<p><strong>Channels kept:</strong> {len(channels_added)}</p>
<p><strong>Programs kept:</strong> {programs_kept}</p>
<p><strong>Final merged file size:</strong> {file_size_mb} MB</p>
<h2>Channels:</h2>
<ul>
"""

for ch in sorted(channels_list):
    html_content += f"<li>{ch}</li>\n"

html_content += "</ul></body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("EPG merge complete!")
print(f"Channels: {len(channels_added)}, Programs: {programs_kept}, Size: {file_size_mb} MB")

