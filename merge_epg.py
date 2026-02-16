import requests
import gzip
import io
from lxml import etree
from datetime import datetime, timedelta
import pytz
import os

# -----------------------
# CONFIG: EPG SOURCES
# -----------------------
EPG_SOURCES = [
    # US feeds
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",

    # India feeds
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",

    # Egypt feeds
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",

    # Lebanon feed
    "https://iptv-epg.org/files/epg-lb.xml.gz",
]

# -----------------------
# MATCH KEYWORD LISTS
# -----------------------
US_LOCAL_IDS = ["WRC", "WTTG", "WJLA", "WHUT", "WUSA", "WDCA", "WDCW"]
INDIAN_KEYS = [
    "balle", "b4u", "9x jalwa", "mtv india", "travel xp",
    "showbox", "filmy", "dangal", "india tv", "star plus",
    "colors tv", "zee tv", "sony entertainment", "sab tv",
    "aaj tak", "news18", "ndtv", "epic tv", "bindass", "movie plus"
]
EGYPT_MENA_KEYS = [
    "mbc masr", "mbc masr 2", "mbc bollywood", "mbc 2",
    "rotana", "rotana cinema", "rotana movies+", "cbc",
    "on drama", "sada el balad", "mehwar", "utv", "mix one",
    "nile", "egyptian tv", "al hayat", "al nahar", "al kahera",
    "al sharqiya", "bein", "roya", "nessma", "osn tv", "aghani tv"
]

# -----------------------
# UTILITY FUNCTIONS
# -----------------------
def channel_matches(channel_name, channel_id):
    """
    Return True if the channel should be kept based on criteria.
    """
    name_lower = channel_name.lower()
    east_coast = "east" in name_lower and "west" not in name_lower
    local_us = any(loc.lower() in channel_id.lower() for loc in US_LOCAL_IDS)
    indian_match = any(key in name_lower for key in INDIAN_KEYS)
    mena_match = any(key in name_lower for key in EGYPT_MENA_KEYS)
    return east_coast or local_us or indian_match or mena_match

# -----------------------
# DOWNLOAD, MERGE, TRACK POPULAR
# -----------------------
merged_root = etree.Element("tv")
channels_added = set()
channels_list = []
channel_frequency = {}  # track channel name occurrences across sources
programs_kept = 0

for url in EPG_SOURCES:
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

            key_name = ch_name.lower()
            channel_frequency[key_name] = channel_frequency.get(key_name, 0) + 1

            if channel_matches(ch_name, ch_id) and ch_id not in channels_added:
                merged_root.append(ch)
                channels_added.add(ch_id)
                channels_list.append(ch_name)

        # Programs
        cutoff = datetime.now(pytz.utc) - timedelta(days=3)
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
# ADD POPULAR CHANNELS AUTOMATICALLY
# -----------------------
popular_threshold = 2  # appears in 2+ sources
for ch_name, count in channel_frequency.items():
    if count >= popular_threshold and ch_name not in [c.lower() for c in channels_list]:
        # Add this popular channel if we can find it in any source
        for url in EPG_SOURCES:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            with gzip.open(io.BytesIO(r.content), "rb") as f:
                tree = etree.parse(f)
                root = tree.getroot()
                for ch in root.findall("channel"):
                    names = [d.text.lower() for d in ch.findall("display-name") if d.text]
                    if ch_name in names and ch.get("id") not in channels_added:
                        merged_root.append(ch)
                        channels_added.add(ch.get("id"))
                        channels_list.append(ch_name.title())
                        break

# -----------------------
# WRITE merged.xml.gz
# -----------------------
tree = etree.ElementTree(merged_root)
with gzip.open("merged.xml.gz", "wb") as f:
    tree.write(f, encoding="UTF-8", xml_declaration=True)

file_size_mb = round(os.path.getsize("merged.xml.gz") / (1024 * 1024), 2)

# -----------------------
# WRITE index.html STATUS
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

