#!/usr/bin/env python3
import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
import os

# ---------------- Sources ----------------
sources = {
    # US feeds
    "US2": {
        "txt": "https://epgshare01.online/epgshare01/us2.txt",
        "xml": "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
        "us_rules": True
    },
    "US_LOCALS1": {
        "txt": "https://epgshare01.online/epgshare01/us_locals1.txt",
        "xml": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
        "us_rules": False  # always include all channels
    },
    "UnitedStates10": {
        "txt": "https://epgshare01.online/epgshare01/unitedstates10.txt",
        "xml": "https://www.open-epg.com/files/unitedstates10.xml.gz",
        "us_rules": True
    },

    # Foreign feeds
    "Egypt": {
        "txt": "https://epgshare01.online/epgshare01/egypt.txt",
        "xml": ["https://iptv-epg.org/files/epg-eg.xml.gz",
                "https://www.open-epg.com/files/egypt1.xml.gz",
                "https://www.open-epg.com/files/egypt2.xml.gz"],
        "us_rules": False
    },
    "Lebanon": {
        "txt": "https://epgshare01.online/epgshare01/lebanon.txt",
        "xml": ["https://iptv-epg.org/files/epg-lb.xml.gz"],
        "us_rules": False
    },
    "India": {
        "txt": "https://epgshare01.online/epgshare01/india.txt",
        "xml": ["https://iptv-epg.org/files/epg-in.xml.gz",
                "https://www.open-epg.com/files/india3.xml.gz"],
        "us_rules": False
    },
}

# ---------------- Indian Channels ----------------
# Only popular Indian channels you asked for
indian_channels = [
    "star plus", "star bharat", "star gold", "star sports",
    "zee tv", "zee cinema", "zee news",
    "sony entertainment", "sony sab", "sony max",
    "colors", "colors cineplex",
    "b4u", "b4u movies", "b4u music",
    "balle balle", "9x jalwa", "mtv india"
]

# ---------------- Helper functions ----------------
def keep_us_channel(channel_name):
    """US rule: keep East channels or channels without East/West"""
    name_lower = channel_name.lower()
    return "east" in name_lower or ("east" not in name_lower and "west" not in name_lower)

def fetch_txt_channels(url):
    """Return set of channel names from TXT file"""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return set(line.strip() for line in r.text.splitlines() if line.strip())
    except Exception as e:
        print(f"TXT fetch failed for {url}: {e}")
        return set()

def fetch_xml_channels_and_programs(urls, us_rules=False):
    """Return channels dict and programs dict from XML/GZ sources"""
    channels = {}
    programs = {}
    if isinstance(urls, str):
        urls = [urls]
    for url in urls:
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            content = gzip.decompress(r.content)
            tree = ET.parse(BytesIO(content))
            root = tree.getroot()
            # Channels
            for ch in root.findall('channel'):
                ch_id = ch.get('id')
                ch_name_el = ch.find('display-name')
                if ch_id and ch_name_el is not None:
                    ch_name = ch_name_el.text.strip()
                    if us_rules and not keep_us_channel(ch_name):
                        continue
                    if ch_id not in channels:
                        channels[ch_id] = ET.tostring(ch, encoding='unicode')
            # Programs
            for pr in root.findall('programme'):
                pr_channel = pr.get('channel')
                pr_title_el = pr.find('title')
                pr_title = pr_title_el.text.strip() if pr_title_el is not None else ""
                pr_id = f"{pr_channel}_{pr_title}"
                if pr_id not in programs:
                    programs[pr_id] = ET.tostring(pr, encoding='unicode')
        except Exception as e:
            print(f"XML fetch failed for {url}: {e}")
    return channels, programs

# ---------------- Main merge ----------------
all_channels = {}
all_programs = {}

for feed, info in sources.items():
    # 1️⃣ Try TXT first
    txt_channels = fetch_txt_channels(info.get("txt"))
    if txt_channels:
        for ch_name in txt_channels:
            # Filter US feeds by rule
            if info.get("us_rules", False) and not keep_us_channel(ch_name):
                continue
            ch_id = f"{feed}_{ch_name.lower()}"
            if ch_id not in all_channels:
                ch_el = ET.Element("channel", id=ch_id)
                ET.SubElement(ch_el, "display-name").text = ch_name
                all_channels[ch_id] = ET.tostring(ch_el, encoding='unicode')
        # Programs are skipped for TXT (you only get channel list)
        continue  # skip XML if TXT exists

    # 2️⃣ Fallback to XML/GZ
    channels, programs = fetch_xml_channels_and_programs(info.get("xml", []), info.get("us_rules", False))
    all_channels.update(channels)
    all_programs.update(programs)

# 3️⃣ Add Indian channels manually if missing
for ch_name in indian_channels:
    ch_id = f"india_{ch_name.lower()}"
    if ch_id not in all_channels:
        ch_el = ET.Element("channel", id=ch_id)
        ET.SubElement(ch_el, "display-name").text = ch_name
        all_channels[ch_id] = ET.tostring(ch_el, encoding='unicode')

# ---------------- Build final XML ----------------
root = ET.Element("tv")

for ch_xml in all_channels.values():
    root.append(ET.fromstring(ch_xml))

for pr_xml in all_programs.values():
    root.append(ET.fromstring(pr_xml))

final_xml = ET.tostring(root, encoding='utf-8')

# ---------------- Write to merged file ----------------
merged_file = "merged.xml.gz"
with gzip.open(merged_file, "wb") as f:
    f.write(final_xml)

# ---------------- Stats ----------------
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
channels_count = len(all_channels)
programs_count = len(all_programs)
file_size_mb = round(len(final_xml) / (1024 * 1024), 2)

print(f"EPG Merge Status")
print(f"Last updated: {timestamp}")
print(f"Channels kept: {channels_count}")
print(f"Programs kept: {programs_count}")
print(f"Final merged file size: {file_size_mb} MB")

