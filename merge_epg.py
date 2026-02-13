#!/usr/bin/env python3
import gzip
import requests
from lxml import etree
from datetime import datetime
import pytz

# --- CONFIG ---
OUTPUT_XML_GZ = "merged.xml.gz"
TIMEZONE = "America/New_York"  # local time zone for display

# Channels to keep (local DC/MD/VA + key internationals)
KEEP_CHANNELS = [
    # DC/MD/VA locals
    "WRC", "WRC-HD", "WUSA", "WUSA-HD", "WJLA", "WJLA-TV", "WTTG", "WDCA",
    "WFDC-DT", "WDCW", "WETA", "WMPT", "WZDC", "WHUT",
    # Key international channels
    "MBC MASR", "MBC MASR 2", "MBC 1 Aghani", "Nogoum", "Balle Balle",
    "9X Jalwa", "MTV India"
]

# --- SOURCES ---
EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

# --- MERGE LOGIC ---
all_channels = {}
all_programs = []

for url in EPG_SOURCES:
    print(f"Downloading {url} ...")
    resp = requests.get(url, timeout=None)  # no timeout, will wait until complete
    resp.raise_for_status()

    with gzip.GzipFile(fileobj=resp.raw) as f:
        tree = etree.parse(f)

    # Extract channels
    for ch in tree.xpath("//channel"):
        ch_id = ch.get("id")
        display_name = ch.findtext("display-name")
        if any(k.lower() in (display_name or "").lower() for k in KEEP_CHANNELS):
            all_channels[ch_id] = ch

    # Extract programs
    for pr in tree.xpath("//programme"):
        if pr.get("channel") in all_channels:
            all_programs.append(pr)

# --- WRITE MERGED XML ---
tv = etree.Element("tv")
for ch in all_channels.values():
    tv.append(ch)
for pr in all_programs:
    tv.append(pr)

# Add last updated time in local timezone
local_time = datetime.now(pytz.timezone(TIMEZONE))
tv.set("lastUpdated", local_time.strftime("%Y-%m-%d %H:%M:%S %Z"))

with gzip.open(OUTPUT_XML_GZ, "wb") as f:
    f.write(etree.tostring(tv, pretty_print=True, xml_declaration=True, encoding="UTF-8"))

print(f"EPG merge completed\nLast updated: {local_time}\nChannels kept: {len(all_channels)}\nPrograms kept: {len(all_programs)}")

