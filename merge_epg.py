#!/usr/bin/env python3
import gzip
import requests
from lxml import etree

# Example: download multiple EPGs and merge
epg_urls = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

output_file = "output/merged.xml.gz"
all_channels = []

for url in epg_urls:
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with gzip.open(r.content, 'rb') as f:
        tree = etree.parse(f)
        all_channels.append(tree)

# For simplicity, just pick the first XML as the merged root
merged_root = all_channels[0].getroot()

# TODO: You can add logic to append missing channels here

# Write merged XML to gzip
with gzip.open(output_file, "wb") as f_out:
    f_out.write(etree.tostring(merged_root, xml_declaration=True, encoding="UTF-8"))

print(f"Merged EPG saved to {output_file}")

