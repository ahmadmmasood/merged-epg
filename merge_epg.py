#!/usr/bin/env python3
import gzip
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime

# ---------------- Config ----------------
epg_sources = {
    # Local US
    "us_locals": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "us_main": "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "us_extra": "https://www.open-epg.com/files/unitedstates10.xml.gz",
    # Foreign
    "egypt1": "https://iptv-epg.org/files/epg-eg.xml.gz",
    "egypt2": "https://www.open-epg.com/files/egypt2.xml.gz",
    "lebanon": "https://iptv-epg.org/files/epg-lb.xml.gz",
    "india1": "https://iptv-epg.org/files/epg-in.xml.gz",
    "india2": "https://www.open-epg.com/files/india3.xml.gz",
}

# ---------------- Channel Filters ----------------
# Only include East or channels without East/West for US main feeds
def us_filter(name):
    name_lower = name.lower()
    return "east" in name_lower or ("east" not in name_lower and "west" not in name_lower)

# Indian channels (foreign)
INDIAN_CHANNELS = [
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
]

# Channels to always include from foreign feeds
MANDATORY_CHANNELS = [
    "aghani", "nogoum", "mbc masr", "mbc masr2", "mbc1"
]

# ---------------- Helper Functions ----------------
def fetch_xml_gz(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return gzip.decompress(r.content)

def parse_xml(xml_bytes):
    return ET.fromstring(xml_bytes)

def merge_channels(feeds):
    seen_channels = set()
    merged_root = ET.Element("tv")
    programs_count = 0

    for feed_name, url in feeds.items():
        xml_bytes = fetch_xml_gz(url)
        root = parse_xml(xml_bytes)
        for channel in root.findall("channel"):
            ch_id = channel.get("id")
            ch_name = (channel.findtext("display-name") or "").strip().lower()
            # Filters for US main/extra feeds
            if feed_name in ["us_main", "us_extra"]:
                if not us_filter(ch_name):
                    continue
            # For other feeds, filter only mandatory or Indian channels
            if feed_name in ["india1","india2"]:
                if ch_name not in INDIAN_CHANNELS and ch_name not in MANDATORY_CHANNELS:
                    continue
            if ch_id in seen_channels:
                continue
            seen_channels.add(ch_id)
            merged_root.append(channel)

        # Add programs
        for prog in root.findall("programme"):
            ch_ref = prog.get("channel")
            if ch_ref in seen_channels:
                merged_root.append(prog)
                programs_count += 1

    return merged_root, seen_channels, programs_count

def write_gz(xml_root, filename):
    xml_str = ET.tostring(xml_root, encoding="utf-8")
    with gzip.open(filename, "wb") as f:
        f.write(xml_str)

def write_index(num_channels, num_programs):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    html_content = f"""
<html>
<head><title>EPG Merge Status</title></head>
<body>
<h2>EPG Merge Status</h2>
<p>Last updated: {timestamp}</p>
<p>Channels kept: {num_channels}</p>
<p>Programs kept: {num_programs}</p>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

# ---------------- Main ----------------
if __name__ == "__main__":
    merged_root, channels_set, programs_count = merge_channels(epg_sources)
    write_gz(merged_root, "merged.xml.gz")
    write_index(len(channels_set), programs_count)
    print(f"Merged EPG written: {len(channels_set)} channels, {programs_count} programs")

