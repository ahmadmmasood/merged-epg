import gzip
import requests
import pytz
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

# ---------------- Sources ----------------
sources = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz"
]

# ---------------- Indian Channels ----------------
indian_channels = [
    "b4u balle balle", "b4u movies", "9x jalwa", "9x", "mtv india", "zee tv", "zee cinema", "zee news"
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
log_output = ""

# Fetch channels and programs
for url in sources:
    try:
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
                ch_name = ch_name_el.text.strip().lower()
                if any(channel in ch_name for channel in indian_channels):
                    if ch_id not in all_channels:
                        all_channels[ch_id] = ET.tostring(ch, encoding='unicode')

        # Process programs
        for pr in root.findall('programme'):
            pr_channel = pr.get('channel')
            pr_title_el = pr.find('title')
            if pr_title_el is not None:
                pr_title = pr_title_el.text.strip()
                pr_id = f"{pr_channel}_{pr_title}"
                if pr_id not in all_programs:
                    all_programs[pr_id] = ET.tostring(pr, encoding='unicode')

    except Exception as e:
        log_output += f"Error fetching/parsing {url}: {e}\n"

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
eastern_time = pytz.timezone('US/Eastern')
timestamp = datetime.now(eastern_time).strftime("%Y-%m-%d %H:%M:%S %Z")
channels_count = len(all_channels)
programs_count = len(all_programs)
file_size_mb = round(len(final_xml) / (1024 * 1024), 2)

log_output += f"\nEPG Merge Status\n"
log_output += f"Last updated: {timestamp}\n"
log_output += f"Channels kept: {channels_count}\n"
log_output += f"Programs kept: {programs_count}\n"
log_output += f"Final merged file size: {file_size_mb} MB\n"

# ---------------- Update index.html ----------------
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
    <h3>Logs:</h3>
    <details>
        <summary>Show Logs</summary>
        <pre>{log_output}</pre>
    </details>
</body>
</html>
"""

# Save index.html
with open("index.html", "w") as f:
    f.write(index_content)

print(f"Updated index.html with timestamp: {timestamp}")

