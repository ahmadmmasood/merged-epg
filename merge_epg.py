#!/usr/bin/env python3
import gzip
import requests
from lxml import etree
from io import BytesIO
import os

# Output folder
os.makedirs("output", exist_ok=True)
output_file = "output/merged.xml.gz"

# URLs of EPGs to merge
epg_urls = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",       # US main
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",# US locals East Coast
    "https://iptv-epg.org/files/epg-in.xml.gz",                          # India
    "https://www.open-epg.com/files/india3.xml.gz",                       # India
    "https://www.open-epg.com/files/unitedstates10.xml.gz"               # US extra
]

# Channels you specifically want to include (extra / missing)
missing_channels = [
    "ahgani tv", "arabica tv", "balle balle", "jalwa 9x", "love nature",
    "nagoumfmtb", "mbc masr", "mbc masr2", "mbc1", "b4u"
]

# Premium channels to preserve
premium_channels = [
    "HBO", "Max", "Showtime", "Starz", "A&E", "HGTV", "AMC", "Comedy Central"
]

all_trees = []

for url in epg_urls:
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with gzip.open(BytesIO(r.content), 'rb') as f:
        tree = etree.parse(f)
        all_trees.append(tree)

# Merge all channels into first XML
merged_root = all_trees[0].getroot()

# Helper: check if a channel exists by name
def channel_exists(root, name):
    for ch in root.findall(".//channel"):
        if ch.get("name") and name.lower() in ch.get("name").lower():
            return True
    return False

# Add missing channels from all other trees
for tree in all_trees[1:]:
    for ch in tree.findall(".//channel"):
        name = ch.get("name", "")
        if any(x.lower() in name.lower() for x in missing_channels + premium_channels):
            if not channel_exists(merged_root, name):
                merged_root.append(ch)

# Write merged XML to gzip
with gzip.open(output_file, "wb") as f_out:
    f_out.write(etree.tostring(merged_root, xml_declaration=True, encoding="UTF-8"))

print(f"Merged EPG saved to {output_file}")

