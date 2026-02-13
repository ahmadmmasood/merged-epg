#!/usr/bin/env python3
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
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

# East Coast channels (add or remove based on your need)
KEEP_CHANNELS = [
    "WRC-TV", "WZDC-CD", "WTTG", "WDCA", "WJLA-TV", "WHUT-TV",
    "WUSA", "WJAL", "WFDC-DT", "WDCW", "WMPT", "WETA-TV",
    "WRZB-LD", "WDVM-TV", "WPXW-TV", "WDWA-LD", "WMDO-CD",
    # Add more East Coast-specific channels here
]

# Number of days to keep EPG data
DAYS_TO_KEEP = 5

# Output files
OUTPUT_XML = "merged.xml.gz"
OUTPUT_HTML = "index.html"

# Local Time Zone (Adjust if needed)
LOCAL_TZ = pytz.timezone("America/New_York")

# -----------------------
# DOWNLOAD AND MERGE
# -----------------------
merged_root = etree.Element("tv")
channels_added = set()
programs_kept = 0

# Process each EPG source
for url in EPG_SOURCES:
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=None)
    r.raise_for_status()

    with gzip.open(io.BytesIO(r.content), "rb") as f:
        tree = etree.parse(f)
        root = tree.getroot()

        # Process Channels
        for ch in root.findall("channel"):
            ch_id = ch.get("id")
            if ch_id in KEEP_CHANNELS and ch_id not in channels_added:
                merged_root.append(ch)
                channels_added.add(ch_id)

        # Process Programs
        cutoff = datetime.now(pytz.utc) - timedelta(days=DAYS_TO_KEEP)
        for prog in root.findall("programme"):
            ch_id = prog.get("channel")
            start_str = prog.get("start")  # e.g., '20260213200000 +0000'
            if not ch_id or ch_id not in KEEP_CHANNELS:
                continue
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
with gzip.open(OUTPUT_XML, "wb") as f:
    tree.write(f, encoding="UTF-8", xml_declaration=True)

# Get the file size of the merged XML file
file_size = os.path.getsize(OUTPUT_XML)  # Get size in bytes
file_size_mb = file_size / (1024 * 1024)  # Convert to MB
print(f"Final merged XML file size: {file_size_mb:.2f} MB")

# -----------------------
# WRITE INDEX.HTML
# -----------------------
now_local = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

html_content = f"""
<!DOCTYPE html>
<html>
<head>
<title>EPG Merge Status</title>
<meta charset="UTF-8">
</head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {now_local}</p>
<p><strong>Channels kept:</strong> {len(channels_added)}</p>
<p><strong>Programs kept:</strong> {programs_kept}</p>
<p><strong>Final merged file size:</strong> {file_size_mb:.2f} MB</p>
</body>
</html>
"""

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"EPG merge completed")
print(f"Last updated: {now_local}")
print(f"Channels kept: {len(channels_added)}")
print(f"Programs kept: {programs_kept}")
print(f"Final merged XML file size: {file_size_mb:.2f} MB")

