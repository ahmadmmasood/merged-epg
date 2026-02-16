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

    # Additional Channels (B4U, MTV India, etc.)
    "b4u balle balle",
    "9x jalwa",
    "mtv india",
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
log_list = []  # To capture logs

for url in sources:
    try:
        if "epgshare01" in url and url.endswith(".txt"):
            # Fetch the TXT file first
            response = requests.get(url)
            response.raise_for_status()
            log_list.append(f"TXT fetch successful for {url}")
        elif url.endswith(".xml.gz"):
            # Fetch the XML.GZ files
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
                    if "epg_ripper_US2" in url or "unitedstates10" in url:
                        if not keep_us_channel(ch_name):
                            continue
                    # Deduplicate by channel ID
                    if ch_id not in all_channels:
                        all_channels[ch_id] = ET.tostring(ch, encoding='unicode')

            # Process programs
            for pr in root.findall('programme'):
                pr_title_el = pr.find('title')
                if pr_title_el is not None:
                    pr_title = pr_title_el.text.strip()
                    pr_id = f"{pr.get('channel')}_{pr_title}"
                    if pr_id not in all_programs:
                        all_programs[pr_id] = ET.tostring(pr, encoding='unicode')

            log_list.append(f"Processing XML: {url}")

    except Exception as e:
        log_list.append(f"Error fetching/parsing {url}: {str(e)}")

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

log_list.append(f"EPG Merge Status")
log_list.append(f"Last updated: {timestamp}")
log_list.append(f"Channels kept: {channels_count}")
log_list.append(f"Programs kept: {programs_count}")
log_list.append(f"Final merged file size: {file_size_mb} MB")

# Update the logs and index.html
logs = "\n".join(log_list)

# ---------------- Create HTML Content ----------------
html_content = f"""
<html>
<head><title>EPG Merge Status</title></head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {timestamp}</p>
<p><strong>Channels kept:</strong> {channels_count}</p>
<p><strong>Programs kept:</strong> {programs_count}</p>
<p><strong>Final merged file size:</strong> {file_size_mb} MB</p>
<h2>Logs:</h2>
<button onclick="document.getElementById('logs').style.display='block'">Show Logs</button>
<button onclick="document.getElementById('logs').style.display='none'">Hide Logs</button>
<div id="logs" style="display:none;">
    <pre>{logs}</pre>
</div>
</body>
</html>
"""

with open("index.html", "w") as index_file:
    index_file.write(html_content)

print("\n".join(log_list))

