import requests
import gzip
import io
from lxml import etree
from datetime import datetime, timedelta
import pytz
import os
import re

# -----------------------
# CONFIG
# -----------------------

FEEDS = [
    # US
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",

    # International
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
]

# Force-include keywords (if found in feeds)
FORCE_KEYWORDS = [
    "mbc1",
    "mbc 1",
    "mbc masr",
    "mbc masr 2",
    "masr2",
    "aghani",
    "nogoum"
]

# Keep only 48 hours to stay small
HOURS_LIMIT = 48

# -----------------------
# HELPERS
# -----------------------

def download_xml(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return gzip.open(io.BytesIO(r.content), "rb")

def is_west(name):
    return "west" in name.lower()

def normalize_name(name):
    name = name.lower()
    name = re.sub(r"\b(east|west|hd)\b", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

def is_force_channel(name):
    name_lower = name.lower()
    return any(keyword in name_lower for keyword in FORCE_KEYWORDS)

# -----------------------
# MERGE
# -----------------------

merged_root = etree.Element("tv")

channel_ids = set()
channel_names = set()
program_keys = set()

programs_kept = 0
cutoff = datetime.now(pytz.utc)
future_limit = cutoff + timedelta(hours=HOURS_LIMIT)

print("Starting EPG merge...")

for url in FEEDS:
    print(f"Downloading {url}")

    try:
        with download_xml(url) as f:
            tree = etree.parse(f)
            root = tree.getroot()

            # Channels
            for ch in root.findall("channel"):
                ch_id = ch.get("id")
                display = ch.find("display-name")
                ch_name = display.text if display is not None else ""

                if not ch_name:
                    continue

                # ❌ Skip West always
                if is_west(ch_name):
                    continue

                norm = normalize_name(ch_name)

                # Avoid duplicates unless force channel
                if norm in channel_names and not is_force_channel(ch_name):
                    continue

                merged_root.append(ch)
                channel_ids.add(ch_id)
                channel_names.add(norm)

            # Programs
            for prog in root.findall("programme"):
                ch_id = prog.get("channel")
                if ch_id not in channel_ids:
                    continue

                start_str = prog.get("start")
                try:
                    start_time = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
                    start_time = pytz.utc.localize(start_time)
                except:
                    continue

                # Keep only 48 hours forward
                if cutoff <= start_time <= future_limit:
                    key = (ch_id, start_str)
                    if key in program_keys:
                        continue

                    merged_root.append(prog)
                    program_keys.add(key)
                    programs_kept += 1

    except Exception as e:
        print(f"Failed to process {url}: {e}")

# -----------------------
# WRITE OUTPUT
# -----------------------

tree = etree.ElementTree(merged_root)
with gzip.open("merged.xml.gz", "wb") as f:
    tree.write(f, encoding="UTF-8", xml_declaration=True)

size_mb = round(os.path.getsize("merged.xml.gz") / (1024 * 1024), 2)

print("EPG merge complete!")
print(f"Channels: {len(channel_ids)}")
print(f"Programs kept: {programs_kept}")
print(f"Final file size: {size_mb} MB")

