#!/usr/bin/env python3
import requests, gzip, io, os
from lxml import etree
from datetime import datetime, UTC

# ============================
# REQUIRED CORE FEEDS
# ============================
CORE_FEEDS = {
    "EPG 1": "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "EPG 2": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "Indian 1": "https://iptv-epg.org/files/epg-in.xml.gz",
    "Indian 2": "https://www.open-epg.com/files/india3.xml.gz",
    "Digital TV": "https://www.open-epg.com/files/unitedstates10.xml.gz",
}

# ============================
# LOCAL REGION KEYWORDS
# ============================
LOCAL_KEYWORDS = [
    "washington", "dc", "wrc", "wttg", "wusa",
    "baltimore", "wbal", "wjz", "maryland",
    "northern virginia", "arlington", "fairfax"
]

# ============================
# EAST COAST FILTER
# ============================
EAST_MARKERS = ["east", "-e", "et", "est"]
WEST_MARKERS = ["west", "-w", "pt", "mt", "ct", "pacific", "mountain"]

# ============================
# SPORTS KEYWORDS
# ============================
SPORTS_KEYWORDS = [
    "espn", "fox sports", "nbc sports",
    "mlb", "nfl", "nba", "nhl",
    "sec", "acc", "big ten"
]

# ============================
# Output paths (root)
# ============================
status_file = "index.html"
merged_file = "merged.xml.gz"

# Write initial status page
with open(status_file, "w") as f:
    f.write(f"<html><body><h1>EPG merge in progress</h1>"
            f"<p>Started at {datetime.now(UTC)} UTC</p></body></html>\n")

# ============================
# FETCH XML
# ============================
def fetch_xml(url):
    print(f"Downloading {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    if url.endswith(".gz"):
        with gzip.open(io.BytesIO(r.content), "rb") as f:
            return etree.parse(f)
    else:
        return etree.ElementTree(etree.fromstring(r.content))

# ============================
# CHANNEL FILTER
# ============================
def keep_channel(display_names):
    name_str = " ".join(display_names).lower()
    # 1. Keep all sports
    if any(sport in name_str for sport in SPORTS_KEYWORDS):
        return True
    # 2. Local DC/MD/VA
    if any(local in name_str for local in LOCAL_KEYWORDS):
        return True
    # 3. East Coast premium/regular
    if any(marker in name_str for marker in EAST_MARKERS):
        if not any(marker in name_str for marker in WEST_MARKERS):
            return True
    return False

# ============================
# MERGE FEEDS
# ============================
all_channels = {}
all_programmes = []
programme_keys = set()

for name, url in CORE_FEEDS.items():
    try:
        tree = fetch_xml(url)
        print(f"Processing {name}")
        for ch in tree.xpath("//channel"):
            ch_id = ch.get("id")
            display_names = ch.xpath("display-name/text()")
            if not display_names:
                continue
            if keep_channel(display_names):
                if ch_id not in all_channels:
                    all_channels[ch_id] = ch
        for prog in tree.xpath("//programme"):
            ch_id = prog.get("channel")
            if ch_id in all_channels:
                key = (ch_id, prog.get("start"))
                if key not in programme_keys:
                    programme_keys.add(key)
                    all_programmes.append(prog)
    except Exception as e:
        print(f"Failed {name}: {e}")

# ============================
# BUILD FINAL XML
# ============================
root = etree.Element("tv")
for ch in all_channels.values():
    root.append(ch)
for prog in all_programmes:
    root.append(prog)

with gzip.open(merged_file, "wb", compresslevel=9) as f:
    f.write(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))

# Write final status page
with open(status_file, "w") as f:
    f.write(f"<html><body><h1>EPG merge completed</h1>"
            f"<p>Last updated: {datetime.now(UTC)} UTC</p>"
            f"<p>Channels kept: {len(all_channels)}</p>"
            f"<p>Programs kept: {len(all_programmes)}</p>"
            f"</body></html>\n")

print("Regional optimized merge complete.")

