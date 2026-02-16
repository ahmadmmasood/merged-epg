import os
import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

# ---------------- Sources ----------------
sources = [
    # US feeds
    "https://epgshare01.online/epgshare01/epg_ripper_US2.txt",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.txt",

    # Foreign feeds
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz"
]

# ---------------- Indian Channels ----------------
indian_channels = [
    "b4u balle balle",
    "mtv india",
    "zee tv",
    "zee cinema",
    "zee news",
    "sony entertainment",
    "sony sab",
    "sony max",
    "star plus",
    "star bharat",
    "star gold",
    "star sports",
    "colors",
    "colors cineplex"
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

for url in sources:
    try:
        print(f"Processing {url}...")
        
        # Fetch and parse .txt file if available
        if url.endswith(".txt"):
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            content = r.text.splitlines()

            for line in content:
                ch_name = line.strip().lower()
                if any(indian_channel in ch_name for indian_channel in indian_channels):
                    all_channels[ch_name] = ch_name

        # Fallback to .xml.gz if no .txt file available or if URL is .xml.gz
        elif url.endswith(".xml.gz"):
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            content = gzip.decompress(r.content)
            tree = ET.parse(BytesIO(content))
            root = tree.getroot()

            # Process channels
            for ch in root.findall('channel'):
                ch_name_el = ch.find('display-name')
                if ch_name_el is not None:
                    ch_name = ch_name_el.text.strip().lower()
                    if any(indian_channel in ch_name for indian_channel in indian_channels):
                        all_channels[ch_name] = ch_name

            # Process programs
            for pr in root.findall('programme'):
                pr_channel = pr.get('channel')
                pr_title_el = pr.find('title')
                if pr_channel and pr_title_el is not None:
                    pr_title = pr_title_el.text.strip()
                    if pr_channel in all_channels:
                        pr_id = f"{pr_channel}_{pr_title}"
                        all_programs[pr_id] = pr_title

    except Exception as e:
        print(f"Error fetching/parsing {url}: {e}")

# ---------------- Build final XML ----------------
root = ET.Element("tv")

# Add channels
for ch_name in all_channels.values():
    channel_elem = ET.SubElement(root, "channel")
    display_name_elem = ET.SubElement(channel_elem, "display-name")
    display_name_elem.text = ch_name

# Add programs
for pr_id, pr_title in all_programs.items():
    programme_elem = ET.SubElement(root, "programme", {"channel": pr_id.split("_")[0]})
    title_elem = ET.SubElement(programme_elem, "title")
    title_elem.text = pr_title

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

print(f"EPG Merge Status")
print(f"Last updated: {timestamp}")
print(f"Channels kept: {channels_count}")
print(f"Programs kept: {programs_count}")
print(f"Final merged file size: {file_size_mb} MB")

# ---------------- Update Index HTML ----------------
index_file = "index.html"
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
<p><strong>Logs:</strong> <button onclick="document.getElementById('logs').style.display='block'">Show Logs</button></p>
<div id="logs" style="display:none;">
<pre>{timestamp} - Processing completed with {channels_count} channels and {programs_count} programs.</pre>
</div>
</body>
</html>
"""

with open(index_file, "w") as f:
    f.write(index_content)

print(f"Updated {index_file} with timestamp: {timestamp}")

