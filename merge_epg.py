#!/usr/bin/env python3
import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
import re

# ---------------- Sources ----------------
sources = [
    # US feeds
    ("US2", "https://epgshare01.online/epgshare01/epg_ripper_US2"),
    ("US_LOCALS1", "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1"),
    ("US10", "https://www.open-epg.com/files/unitedstates10"),

    # Foreign feeds (TXT not available, use XML/GZ)
    ("EG1", "https://www.open-epg.com/files/egypt1.xml.gz"),
    ("EG2", "https://www.open-epg.com/files/egypt2.xml.gz"),
    ("EG", "https://iptv-epg.org/files/epg-eg.xml.gz"),
    ("IN1", "https://iptv-epg.org/files/epg-in.xml.gz"),
    ("IN2", "https://www.open-epg.com/files/india3.xml.gz"),
    ("LB", "https://iptv-epg.org/files/epg-lb.xml.gz"),
]

# ---------------- Indian Channels ----------------
indian_channels = [
    # ---------------- Indian ----------------
    # Star Network
    "star plus",
    "star bharat",
    "star gold",
    "star sports",

    # Zee Network
    "zee tv",
    "zee cinema",
    "zee news",

    # Sony Network
    "sony entertainment",
    "sony sab",
    "sony max",

    # Colors / Viacom
    "colors",
    "colors cineplex",

    # B4U Network
    "b4u",
    "balle balle",
    "9x jalwa",
    "mtv india"
]

# ---------------- US East / Local Rules ----------------
def keep_us_channel(channel_name, source_name):
    name_lower = channel_name.lower()
    # Always keep US_LOCALS1 channels
    if "us_locals1" in source_name.lower():
        return True
    # Keep "East" channels or channels without East/West
    return "east" in name_lower or ("east" not in name_lower and "west" not in name_lower)

# ---------------- Prepare data structures ----------------
all_channels = {}
all_programs = {}
logs = []

# ---------------- Helper functions ----------------
def fetch_txt(url_base, source_name):
    """Fetch TXT feed if available"""
    txt_url = f"{url_base}.txt"
    try:
        r = requests.get(txt_url, timeout=15)
        r.raise_for_status()
        logs.append(f"TXT fetched: {txt_url}")
        return r.text.splitlines()
    except Exception as e:
        logs.append(f"TXT fetch failed for {txt_url}: {e}")
        return None

def fetch_xml_gz(url):
    """Fetch XML/GZ feed"""
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        content = gzip.decompress(r.content) if url.endswith(".gz") else r.content
        logs.append(f"XML/GZ fetched: {url}")
        return ET.parse(BytesIO(content)).getroot()
    except Exception as e:
        logs.append(f"XML fetch failed for {url}: {e}")
        return None

# ---------------- Process each source ----------------
for source_name, url_base in sources:
    txt_lines = fetch_txt(url_base, source_name)
    if txt_lines:
        # Only store channel info; no programs in TXT
        for line in txt_lines:
            ch_name = line.strip()
            if not ch_name:
                continue
            ch_id = f"{source_name}_{ch_name}"
            if ch_id not in all_channels:
                all_channels[ch_id] = f"<channel id='{ch_id}'><display-name>{ch_name}</display-name></channel>"
    else:
        # TXT not available, fallback to XML/GZ
        root = fetch_xml_gz(url_base if url_base.endswith(".xml.gz") else f"{url_base}.xml.gz")
        if not root:
            continue

        # Process channels
        for ch in root.findall('channel'):
            ch_id = ch.get('id')
            ch_name_el = ch.find('display-name')
            if ch_id and ch_name_el is not None:
                ch_name = ch_name_el.text.strip()
                # Apply filtering rules
                if source_name in ["US2", "US10"]:
                    if not keep_us_channel(ch_name, source_name):
                        continue
                if ch_name.lower() in [c.lower() for c in indian_channels] or source_name not in ["US2", "US10"]:
                    # Deduplicate by ID
                    if ch_id not in all_channels:
                        all_channels[ch_id] = ET.tostring(ch, encoding='unicode')

        # Process programs
        for pr in root.findall('programme'):
            pr_title_el = pr.find('title')
            if pr_title_el is None:
                continue
            pr_id = f"{pr.get('channel')}_{pr_title_el.text.strip()}"
            if pr_id not in all_programs:
                all_programs[pr_id] = ET.tostring(pr, encoding='unicode')

# ---------------- Build final XML ----------------
root = ET.Element("tv")
for ch_xml in all_channels.values():
    root.append(ET.fromstring(ch_xml))
for pr_xml in all_programs.values():
    root.append(ET.fromstring(pr_xml))

final_xml = ET.tostring(root, encoding='utf-8')

# ---------------- Write merged XML/GZ ----------------
merged_file = "merged.xml.gz"
with gzip.open(merged_file, "wb") as f:
    f.write(final_xml)

# ---------------- Stats ----------------
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
channels_count = len(all_channels)
programs_count = len(all_programs)
file_size_mb = round(len(final_xml) / (1024 * 1024), 2)

logs_text = "\n".join(logs)

# ---------------- Update index.html ----------------
html_content = f"""<!DOCTYPE html>
<html>
<head>
<title>EPG Merge Status</title>
<meta charset="UTF-8">
<style>
  #log {{ display:none; white-space:pre-wrap; background:#f0f0f0; padding:10px; border:1px solid #ccc; }}
  button {{ margin:10px 0; }}
</style>
<script>
function toggleLog() {{
  var x = document.getElementById("log");
  if (x.style.display === "none") {{
    x.style.display = "block";
  }} else {{
    x.style.display = "none";
  }}
}}
</script>
</head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {timestamp}</p>
<p><strong>Channels kept:</strong> {channels_count}</p>
<p><strong>Programs kept:</strong> {programs_count}</p>
<p><strong>Final merged file size:</strong> {file_size_mb} MB</p>

<button onclick="toggleLog()">Show/Hide Logs</button>
<div id="log">
{logs_text}
</div>

</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

# ---------------- Print summary ----------------
print("EPG Merge Status")
print(f"Last updated: {timestamp}")
print(f"Channels kept: {channels_count}")
print(f"Programs kept: {programs_count}")
print(f"Final merged file size: {file_size_mb} MB")
print("Logs written to index.html")

