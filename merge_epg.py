#!/usr/bin/env python3
import gzip
import io
import requests
from lxml import etree
from datetime import datetime
import pytz

# -------------------------
# CONFIG
# -------------------------
SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

MERGED_FILE = "merged.xml.gz"
INDEX_FILE = "index.html"
TIMEZONE = "America/New_York"

# -------------------------
# FUNCTIONS
# -------------------------
def download_gz(url):
    print(f"Downloading {url} ...")
    resp = requests.get(url, stream=True, timeout=None)
    resp.raise_for_status()
    return gzip.decompress(resp.content)

def parse_xml(data):
    return etree.fromstring(data)

def merge_channels(root_elements):
    merged_root = etree.Element("tv")
    channels_seen = set()
    programs_seen = set()

    total_programs = 0
    for root in root_elements:
        # Channels
        for ch in root.findall("channel"):
            ch_id = ch.get("id")
            if ch_id not in channels_seen:
                merged_root.append(ch)
                channels_seen.add(ch_id)

        # Programs
        for prog in root.findall("programme"):
            prog_key = (prog.get("channel"), prog.get("start"), prog.get("stop"))
            if prog_key not in programs_seen:
                merged_root.append(prog)
                programs_seen.add(prog_key)
                total_programs += 1

    return merged_root, len(channels_seen), total_programs

def write_gz(root, filename):
    data = etree.tostring(root, pretty_print=True, encoding="UTF-8", xml_declaration=True)
    with gzip.open(filename, "wb") as f:
        f.write(data)

def update_index(channels_count, programs_count):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    html = f"""<html>
<head><title>EPG Merge Status</title></head>
<body>
<h2>EPG merge completed</h2>
<p>Last updated: {now}</p>
<p>Channels kept: {channels_count}</p>
<p>Programs kept: {programs_count}</p>
</body>
</html>"""
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    xml_roots = []
    for src in SOURCES:
        try:
            data = download_gz(src)
            xml_roots.append(parse_xml(data))
        except Exception as e:
            print(f"Error downloading or parsing {src}: {e}")

    merged_root, ch_count, prog_count = merge_channels(xml_roots)
    write_gz(merged_root, MERGED_FILE)
    update_index(ch_count, prog_count)
    print(f"Merge finished: {ch_count} channels, {prog_count} programs")

