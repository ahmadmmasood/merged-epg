#!/usr/bin/env python3

import gzip
import requests
import lxml.etree as ET
from datetime import datetime
import pytz
import os

# --- CONFIG ---
EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

MERGED_FILE = "merged.xml.gz"
INDEX_FILE = "index.html"
CHUNK_SIZE = 1024 * 1024  # 1 MB chunks

# --- FUNCTIONS ---
def download_gz(url, local_path):
    print(f"Downloading: {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(local_path, "wb") as f:
        total = 0
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                total += len(chunk)
        print(f"Downloaded {total / (1024*1024):.2f} MB")
    return local_path

def load_xml_from_gz(path):
    with gzip.open(path, "rb") as f:
        tree = ET.parse(f)
    return tree

def merge_tvsources(sources):
    merged_root = ET.Element("tv")
    channel_ids = set()
    program_count = 0

    for i, url in enumerate(sources):
        temp_file = f"temp_{i}.xml.gz"
        download_gz(url, temp_file)
        tree = load_xml_from_gz(temp_file)
        root = tree.getroot()

        # Channels
        for ch in root.findall("channel"):
            ch_id = ch.get("id")
            if ch_id not in channel_ids:
                merged_root.append(ch)
                channel_ids.add(ch_id)

        # Programs
        for prog in root.findall("programme"):
            merged_root.append(prog)
            program_count += 1

        os.remove(temp_file)

    return merged_root, len(channel_ids), program_count

def save_merged_xml(root, path):
    tree = ET.ElementTree(root)
    with gzip.open(path, "wb") as f:
        tree.write(f, xml_declaration=True, encoding="UTF-8")
    print(f"Merged XML saved to {path}")

def update_index_html(channels, programs, index_path):
    local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>EPG Merge Status</title>
</head>
<body>
    <h1>EPG merge completed</h1>
    <p>Last updated: {local_time}</p>
    <p>Channels kept: {channels}</p>
    <p>Programs kept: {programs}</p>
</body>
</html>
"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Index updated at {index_path}")

# --- MAIN ---
if __name__ == "__main__":
    merged_root, channel_count, program_count = merge_tvsources(EPG_SOURCES)
    save_merged_xml(merged_root, MERGED_FILE)
    update_index_html(channel_count, program_count, INDEX_FILE)

