#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gzip
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

# ---------------- CONFIG ----------------
MERGED_FILE = Path("merged.xml.gz")

# ---------------- URL SOURCES ----------------
urls = {
    # Local DC channels
    "us_locals": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",

    # US East + misc
    "us_main": [
        "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
        "https://www.open-epg.com/files/unitedstates10.xml.gz"
    ],

    # Foreign
    "egypt": [
        "https://iptv-epg.org/files/epg-eg.xml.gz",
        "https://www.open-epg.com/files/egypt1.xml.gz",
        "https://www.open-epg.com/files/egypt2.xml.gz"
    ],
    "lebanon": ["https://iptv-epg.org/files/epg-lb.xml.gz"],
    "india": [
        "https://iptv-epg.org/files/epg-in.xml.gz",
        "https://www.open-epg.com/files/india3.xml.gz"
    ]
}

# ---------------- SEARCH CHANNELS ----------------
search_channels = [
    # ---------------- Indian ----------------
    "star plus", "star bharat", "star gold", "star sports",
    "zee tv", "zee cinema", "zee news",
    "sony entertainment", "sony sab", "sony max",
    "colors", "colors cineplex",
]

# ---------------- US Merge Rules ----------------
def is_us_channel_valid(channel_name: str) -> bool:
    lower = channel_name.lower()
    if "west" in lower:
        return False
    if "east" in lower or ("east" not in lower and "west" not in lower):
        return True
    return False

# ---------------- UTIL FUNCTIONS ----------------
def fetch_xml_gz(url):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return gzip.decompress(resp.content)

def parse_xml(content):
    return ET.fromstring(content)

# ---------------- MERGE PROCESS ----------------
all_channels = {}
all_programs = []

def merge_feed(content, is_us_feed=False, is_local_feed=False):
    root = parse_xml(content)
    # Channels
    for ch in root.findall("channel"):
        ch_id = ch.attrib.get("id")
        ch_name = ch.findtext("display-name", "").strip()
        if not ch_id or not ch_name:
            continue

        # Local feed: keep all exactly
        if is_local_feed:
            all_channels[ch_id] = ch
            continue

        # US feed rules
        if is_us_feed and not is_us_channel_valid(ch_name):
            continue

        # Foreign: keep only if in search list
        if not is_us_feed and not is_local_feed:
            if ch_name.lower() not in search_channels:
                continue

        # Avoid duplicates
        if ch_id not in all_channels:
            all_channels[ch_id] = ch

    # Programs
    for prg in root.findall("programme"):
        ch_id = prg.attrib.get("channel")
        if not ch_id or ch_id not in all_channels:
            continue
        # Avoid duplicates based on channel + start + title
        prg_id = (
            ch_id,
            prg.attrib.get("start", ""),
            prg.findtext("title", "").strip()
        )
        if prg_id not in all_programs:
            all_programs.append(prg_id)
            # Attach element for writing
            all_channels.setdefault("_programs", []).append(prg)

# ---------------- FETCH AND MERGE ----------------
# Local feed: must include all
local_content = fetch_xml_gz(urls["us_locals"])
merge_feed(local_content, is_local_feed=True)

# US feeds: combine with rules
for url in urls["us_main"]:
    content = fetch_xml_gz(url)
    merge_feed(content, is_us_feed=True)

# Foreign feeds
for country, feed_urls in urls.items():
    if country in ("us_locals", "us_main"):
        continue
    for url in feed_urls:
        content = fetch_xml_gz(url)
        merge_feed(content)

# ---------------- WRITE MERGED FILE ----------------
root_elem = ET.Element("tv")

# Channels
for ch_id, ch_elem in all_channels.items():
    if ch_id == "_programs":
        continue
    root_elem.append(ch_elem)

# Programs
for ch_id in all_channels:
    for prg in all_channels.get("_programs", []):
        root_elem.append(prg)

# Write gzipped XML
MERGED_FILE.write_bytes(gzip.compress(ET.tostring(root_elem, encoding="utf-8")))

# ---------------- UPDATE INDEX ----------------
INDEX_FILE = Path("index.html")
index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>EPG Merge Status</title>
</head>
<body>
<h2>EPG Merge Status</h2>
<p><strong>Last updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p><strong>Channels kept:</strong> {len(all_channels) - 1 if "_programs" in all_channels else len(all_channels)}</p>
<p><strong>Programs kept:</strong> {len(all_programs)}</p>
</body>
</html>
"""

INDEX_FILE.write_text(index_content, encoding="utf-8")
print(f"Merged EPG written to {MERGED_FILE}, index.html updated")

