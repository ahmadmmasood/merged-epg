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

# ---------------- Popular Channels ----------------

# ---------------- Indian ----------------
indian_channels = [
    "b4u",
    "b4u movies",
    "b4u music",
    "balle balle",
    "9x jalwa",
    "mtv india",
    "zee tv",
    "zee cinema",
    "zee news",
]

# ---------------- Egyptian / MENA ----------------
foreign_channels = [
    "aghani",
    "nogoum",
    "mbc masr",
    "mbc masr2",
    "mbc1",
]

# ---------------- US East / Local Rules ----------------
def keep_us_channel(channel_name, source_url):
    name_lower = channel_name.lower()
    # Always keep US locals feed channels
    if "us_locals1" in source_url.lower():
        return True
    # Keep "East" channels or ones with neither "East" nor "West"
    return "east" in name_lower or ("east" not in name_lower and "west" not in name_lower)

# ---------------- Build master channel search set ----------------
search_channels = set([c.lower() for c in indian_channels + foreign_channels])

# ---------------- Fetch, parse, and filter ----------------
all_channels = {}
all_programs = {}
active_sources = []

for url in sources:
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        content = gzip.decompress(r.content)
        tree = ET.parse(BytesIO(content))
        root = tree.getroot()

        feed_has_matches = False

        # Process channels
        for ch in root.findall('channel'):
            ch_id = ch.get('id')
            ch_name_el = ch.find('display-name')
            if ch_id and ch_name_el is not None:
                ch_name = ch_name_el.text.strip()
                # US East / Local filtering
                if "us2" in url.lower() or "unitedstates10" in url.lower() or "us_locals1" in url.lower():
                    if not keep_us_channel(ch_name, url):
                        continue
                # Foreign channels filter
                if any(keyword in ch_name.lower() for keyword in search_channels) or "us" in url.lower():
                    feed_has_matches = True
                    if ch_id not in all_channels:
                        all_channels[ch_id] = ET.tostring(ch, encoding='unicode')

        # Process programs
        for pr in root.findall('programme'):
            pr_title = pr.find('title').text if pr.find('title') is not None else ''
            pr_id = f"{pr.get('channel')}_{pr_title}"
            if pr_id not in all_programs:
                all_programs[pr_id] = ET.tostring(pr, encoding='unicode')

        if feed_has_matches:
            active_sources.append(url)

    except Exception as e:
        print(f"Error fetching/parsing {url}: {e}")

# ---------------- Build final XML ----------------
root = ET.Element("tv")

# Add channels
for ch_xml in all_channels.values():
    root.append(ET.fromstring(ch_xml))

# Add programs
for pr_xml in all_programs.values():
    root.append(ET.fromstring(pr_xml))

final_xml = ET.tostring(root, encoding='utf-8')

# ---------------- Write merged XML.GZ ----------------
merged_file = "merged.xml.gz"
with gzip.open(merged_file, "wb") as f:
    f.write(final_xml)

# ---------------- Update index.html ----------------
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
channels_count = len(all_channels)
programs_count = len(all_programs)
file_size_mb = round(len(final_xml) / (1024 * 1024), 2)

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
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(index_html)

# ---------------- Print status ----------------
print("EPG Merge Status")
print(f"Last updated: {timestamp}")
print(f"Channels kept: {channels_count}")
print(f"Programs kept: {programs_count}")
print(f"Final merged file size: {file_size_mb} MB")
print(f"Active sources used: {len(active_sources)}")

