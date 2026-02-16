#!/usr/bin/env python3
import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

# ---------------- Sources ----------------
sources = [
    # US feeds
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",

    # Foreign feeds
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz"
]

# ---------------- Indian Channels ----------------
indian_channels = [
    "b4u", "b4u balle balle", "9x jalwa", "mtv india",
    "star plus", "star bharat", "star gold", "star sports",
    "zee tv", "zee cinema", "zee news", "sony entertainment",
    "sony sab", "sony max", "colors", "colors cineplex"
]

# ---------------- US East / Local Rules ----------------
def keep_us_channel(channel_name):
    name_lower = channel_name.lower()
    # Keep local feed channels always
    if "us_locals1" in channel_name.lower():
        return True
    # Keep "East" channels or ones with neither "East" nor "West"
    return "east" in name_lower or ("east" not in name_lower and "west" not in name_lower)

# ---------------- Fetch and parse XML ----------------
all_channels = {}
all_programs = {}
log_messages = []  # For logging errors and important info

for url in sources:
    try:
        log_messages.append(f"Processing XML: {url}")
        if url.endswith('.xml.gz'):
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            content = gzip.decompress(r.content)
            tree = ET.parse(BytesIO(content))
            root = tree.getroot()

            # Process channels
            for ch in root.findall('channel'):
                ch_id = ch.get('id')
                ch_name_el = ch.find('display-name')
                if ch_id and ch_name_el is not None:
                    ch_name = ch_name_el.text.strip()
                    # Only keep if passes US/local rules or is foreign channel
                    if "epg_ripper_US2" in url or "unitedstates10" in url:
                        if not keep_us_channel(ch_name):
                            continue
                    if any(indian_channel in ch_name.lower() for indian_channel in indian_channels):
                        if ch_id not in all_channels:
                            all_channels[ch_id] = ET.tostring(ch, encoding='unicode')

            # Process programs
            for pr in root.findall('programme'):
                pr_id = f"{pr.get('channel')}_{pr.find('title').text if pr.find('title') is not None else ''}"
                if pr_id not in all_programs:
                    all_programs[pr_id] = ET.tostring(pr, encoding='unicode')

    except Exception as e:
        log_messages.append(f"Error fetching/parsing {url}: {e}")

# ---------------- Build final XML ----------------
root = ET.Element("tv")

# Add channels
for ch_xml in all_channels.values():
    root.append(ET.fromstring(ch_xml))

# Add programs
for pr_xml in all_programs.values():
    root.append(ET.fromstring(pr_xml))

final_xml = ET.tostring(root, encoding='utf-8')

# ---------------- Write to merged file ----------------
merged_file = "merged.xml.gz"
with gzip.open(merged_file, "wb") as f:
    f.write(final_xml)

# ---------------- Stats ----------------
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
channels_count = len(all_channels)
programs_count = len(all_programs)
file_size_mb = round(len(final_xml) / (1024 * 1024), 2)

# Update the index.html file
index_content = f"""
<!DOCTYPE html>
<html>
<head>
<title>EPG Merge Status</title>
<meta charset="UTF-8">
</head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {timestamp}</p>
<p><strong>Channels kept:</strong> {channels_count}</p>
<p><strong>Programs kept:</strong> {programs_count}</p>
<p><strong>Final merged file size:</strong> {file_size_mb} MB</p>
<h2>Logs</h2>
<button onclick="document.getElementById('logDiv').style.display='block'">Show Logs</button>
<div id="logDiv" style="display:none; border: 1px solid #ccc; margin-top: 10px; padding: 10px;">
    <pre>{chr(10).join(log_messages)}</pre>
    <button onclick="document.getElementById('logDiv').style.display='none'">Close</button>
</div>
</body>
</html>
"""

# Write to index.html
with open("index.html", "w") as index_file:
    index_file.write(index_content)

# Print merge status to the console
print(f"EPG Merge Status")
print(f"Last updated: {timestamp}")
print(f"Channels kept: {channels_count}")
print(f"Programs kept: {programs_count}")
print(f"Final merged file size: {file_size_mb} MB")

