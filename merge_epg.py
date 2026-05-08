#!/usr/bin/env python3
import requests
import gzip
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz

# -----------------------------
# CONFIG
# -----------------------------
EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"
MERGED_OUTPUT = "merged.xml"
LOCAL_OUTPUT = "local.xml"
DAYS_TO_KEEP = 3  # Optional: only keep X days of programming

# -----------------------------
# Load master channels for filtering
# -----------------------------
with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
    master_channels = [line.strip() for line in f if line.strip() and not line.startswith("#")]

print(f"Loaded {len(master_channels)} master channels for filtering.")

# -----------------------------
# Fetch all XML sources
# -----------------------------
def fetch_xml(url):
    print(f"Fetching {url} ...")
    r = requests.get(url)
    r.raise_for_status()
    data = r.content
    if url.endswith(".gz"):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            data = gz.read()
    return ET.fromstring(data)

sources = []
with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip()]
    for url in urls:
        try:
            tree = fetch_xml(url)
            sources.append(tree)
        except Exception as e:
            print(f"Error fetching {url}: {e}")

print(f"Fetched {len(sources)} XML sources.")

# -----------------------------
# Merge all channels and programmes
# -----------------------------
merged_root = ET.Element("tv")
channels_dict = {}
programmes_count = 0

for tree in sources:
    for channel in tree.findall("channel"):
        ch_id = channel.get("id")
        if ch_id not in channels_dict:
            merged_root.append(channel)
            channels_dict[ch_id] = channel

    for programme in tree.findall("programme"):
        # Optional: filter by 3 days
        if DAYS_TO_KEEP:
            start_str = programme.get("start")  # format: YYYYMMDDHHMMSS ±HHMM
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            if start_dt > datetime.utcnow() + timedelta(days=DAYS_TO_KEEP):
                continue
        merged_root.append(programme)
        programmes_count += 1

print(f"Total channels fetched: {len(channels_dict)}")
print(f"Total programmes fetched: {programmes_count}")

# -----------------------------
# Save merged XML and GZ
# -----------------------------
merged_tree = ET.ElementTree(merged_root)
merged_tree.write(MERGED_OUTPUT, encoding="utf-8", xml_declaration=True)
with gzip.open(MERGED_OUTPUT + ".gz", "wb") as f:
    f.write(ET.tostring(merged_root, encoding="utf-8"))
print(f"Saved merged XML and {MERGED_OUTPUT}.gz")

# -----------------------------
# Filter local channels
# -----------------------------
local_root = ET.Element("tv")
local_channels_matched = []
local_programmes_count = 0

for ch in channels_dict.values():
    display_name = ch.findtext("display-name")
    if display_name:
        for master_name in master_channels:
            if master_name.lower() in display_name.lower():
                local_root.append(ch)
                local_channels_matched.append(display_name)
                break

for prog in merged_root.findall("programme"):
    ch_id = prog.get("channel")
    if ch_id in [c.get("id") for c in local_root.findall("channel")]:
        local_root.append(prog)
        local_programmes_count += 1

print(f"Local channels matched: {local_channels_matched}")
print(f"Local channels included: {len(local_channels_matched)}")
print(f"Local programmes included: {local_programmes_count}")

# -----------------------------
# Save local XML and GZ
# -----------------------------
local_tree = ET.ElementTree(local_root)
local_tree.write(LOCAL_OUTPUT, encoding="utf-8", xml_declaration=True)
with gzip.open(LOCAL_OUTPUT + ".gz", "wb") as f:
    f.write(ET.tostring(local_root, encoding="utf-8"))
print(f"Saved local XML and {LOCAL_OUTPUT}.gz")
