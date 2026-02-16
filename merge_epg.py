import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
import os

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

# ---------------- Channel Criteria ----------------
indian_channels = [
    "star plus", "star bharat", "star gold", "star sports",  # Star Network
    "zee tv", "zee cinema", "zee news",  # Zee Network
    "sony entertainment", "sony sab", "sony max",  # Sony Network
    "colors", "colors cineplex",  # Colors / Viacom
    "b4u", "b4u movies", "balle balle", "9x jalwa", "mtv india",  # Additional Indian Channels
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

log_messages = []  # List to collect log messages

# Check if txt file exists, else fallback to XML
def fetch_txt_channels(url):
    try:
        txt_url = url.replace(".xml.gz", ".txt")  # Attempt to fetch TXT version
        response = requests.get(txt_url, timeout=15)
        response.raise_for_status()
        return response.text.splitlines()
    except requests.exceptions.RequestException as e:
        log_messages.append(f"TXT fetch failed for {txt_url}: {e}")
        return []

def fetch_xml_channels(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        content = gzip.decompress(r.content)
        tree = ET.parse(BytesIO(content))
        return tree.getroot()
    except Exception as e:
        log_messages.append(f"XML fetch failed for {url}: {e}")
        return None

# Process channels and programs
for url in sources:
    log_messages.append(f"Processing {url}...")
    
    channels = fetch_txt_channels(url)  # Try fetching txt first
    if not channels:  # Fallback to XML if no txt found
        root = fetch_xml_channels(url)
        if root is None:
            continue
        channels = [ch.find('display-name').text.strip() for ch in root.findall('channel')]

    # Process channels
    for channel_name in channels:
        if channel_name:
            # Only keep channels matching our criteria
            if "epg_ripper_US2" in url or "unitedstates10" in url:
                if not keep_us_channel(channel_name):
                    continue
            # Deduplicate channels based on channel name
            if channel_name not in all_channels:
                all_channels[channel_name] = channel_name  # Use name as unique identifier

    # Process programs (only if root is defined and XML file is being processed)
    if root:
        for pr in root.findall('programme'):
            pr_title_el = pr.find('title')
            if pr_title_el is not None:
                pr_title = pr_title_el.text.strip() if pr_title_el.text else ""
                pr_id = f"{pr.get('channel')}_{pr_title}"
                # Only add programs for channels in our list
                if pr_id not in all_programs:
                    all_programs[pr_id] = ET.tostring(pr, encoding='unicode')

# ---------------- Build final XML ----------------
root = ET.Element("tv")

# Add channels
for ch_name in all_channels.values():
    ch_element = ET.Element("channel", id=ch_name)  # Assuming each channel needs a unique id
    root.append(ch_element)

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

# Add the log message to index page
log_messages.append(f"EPG Merge Status\nLast updated: {timestamp}\nChannels kept: {channels_count}\nPrograms kept: {programs_count}\nFinal merged file size: {file_size_mb} MB")

# Print logs to console for debugging
for msg in log_messages:
    print(msg)

# ---------------- Update Index Page ----------------
index_html = f"""<!DOCTYPE html>
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
<p><strong>Logs:</strong> <button onclick="document.getElementById('logs').style.display = 'block';">Show Logs</button></p>
<div id="logs" style="display:none;">
<pre>{chr(10).join(log_messages)}</pre>
</div>
</body>
</html>"""

# Write to index.html (you can change file path if needed)
with open('index.html', 'w') as f:
    f.write(index_html)

