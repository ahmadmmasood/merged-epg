import requests
import gzip
import io
from lxml import etree
from datetime import datetime, timedelta
import pytz
import os

# -----------------------
# CONFIG
# -----------------------
EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz"
]

# Channels to always include by partial match (case insensitive)
INTERNATIONAL_CHANNEL_KEYS = [
    "balle", "b4u", "9x jalwa", "mtv india", "travel xp",
    "aghani", "nogoum", "mbc masr", "mbc1"
]

LOCAL_CHANNEL_IDS = [
    "WRC", "WTTG", "WJLA", "WHUT", "WUSA", "WDCA", "WDCW", "WJAL",
    "WETA", "WPXW", "WDVM", "WMPT"
]

def is_east_coast_or_local_or_international(channel_name, channel_id):
    name_lower = channel_name.lower()

    # East Coast criteria
    east_coast = 'east' in name_lower and 'west' not in name_lower

    # Local broadcast stations
    local = any(local_id.lower() in channel_id.lower() for local_id in LOCAL_CHANNEL_IDS)

    # International channels by partial name match
    international = any(key in name_lower for key in INTERNATIONAL_CHANNEL_KEYS)

    return east_coast or local or international

# -----------------------
# DOWNLOAD AND MERGE
# -----------------------
merged_root = etree.Element("tv")

channels_added = set()
channels_merged = []
programs_kept = 0

for url in EPG_SOURCES:
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=None)
    r.raise_for_status()
    
    with gzip.open(io.BytesIO(r.content), "rb") as f:
        tree = etree.parse(f)
        root = tree.getroot()
        
        # Channels
        for ch in root.findall("channel"):
            ch_id = ch.get("id")
            display_names = [d.text for d in ch.findall("display-name") if d.text]
            ch_name = display_names[0] if display_names else ""

            if is_east_coast_or_local_or_international(ch_name, ch_id) and ch_id not in channels_added:
                merged_root.append(ch)
                channels_added.add(ch_id)
                channels_merged.append(ch_name)

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
# WRITE XML.GZ
# -----------------------
tree = etree.ElementTree(merged_root)
with gzip.open("merged.xml.gz", "wb") as f:
    tree.write(f, encoding="UTF-8", xml_declaration=True)

file_size_mb = round(os.path.getsize("merged.xml.gz") / (1024 * 1024), 2)

# -----------------------
# WRITE STATUS HTML
# -----------------------
now_local = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")

html_content = f"""
<!DOCTYPE html>
<html>
<head><title>EPG Merge Status</title><meta charset="UTF-8"></head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {now_local}</p>
<p><strong>Channels kept:</strong> {len(channels_added)}</p>
<p><strong>Programs kept:</strong> {programs_kept}</p>
<p><strong>Final merged file size:</strong> {file_size_mb} MB</p>

<h2>Channels Merged:</h2>
<ul>
"""

for ch in sorted(channels_merged):
    html_content += f"<li>{ch}</li>\n"

html_content += "</ul></body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("EPG merge completed")
print(f"Channels kept: {len(channels_added)}")
print(f"Programs kept: {programs_kept}")
print(f"File size: {file_size_mb} MB")

