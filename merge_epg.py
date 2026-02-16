#!/usr/bin/env python3
import gzip
import requests
import xml.etree.ElementTree as ET

# ---------------- CONFIG ----------------
FEEDS = [
    # US
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    # Egypt / Lebanon / India
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
]

OUTPUT_FILE = "merged.xml.gz"

# ---------------- CHANNEL FILTERS ----------------
# Channels to always include (Indian feed)
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

# Channels to keep from US feeds
def keep_us_channel(name):
    name_lower = name.lower()
    if "west" in name_lower:
        return False
    if "east" in name_lower or ("east" not in name_lower and "west" not in name_lower):
        return True
    return False

# ---------------- FUNCTIONS ----------------
def fetch_feed(url):
    print(f"Fetching: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return gzip.decompress(r.content)

def parse_feed(data):
    return ET.fromstring(data)

def merge_feeds(feeds):
    merged_channels = {}
    merged_programs = []

    for feed_url in feeds:
        data = fetch_feed(feed_url)
        root = parse_feed(data)

        for ch in root.findall("channel"):
            ch_id = ch.attrib.get("id")
            ch_name = ch.findtext("display-name", "").lower()

            if feed_url.endswith("US_LOCALS1.xml.gz"):
                # always keep all locals
                keep = True
            elif feed_url in [FEEDS[0], FEEDS[1]]:  # US feeds
                keep = keep_us_channel(ch_name)
            else:  # foreign feeds
                keep = ch_name in INDIAN_CHANNELS or "mbc" in ch_name or "nogoum" in ch_name or "aghani" in ch_name

            if keep and ch_id not in merged_channels:
                merged_channels[ch_id] = ch

        for prog in root.findall("programme"):
            ch_id = prog.attrib.get("channel")
            if ch_id in merged_channels:
                merged_programs.append(prog)

    return merged_channels, merged_programs

def write_merged_file(channels, programs, output_file):
    root = ET.Element("tv")
    for ch in channels.values():
        root.append(ch)
    for prog in programs:
        root.append(prog)

    tree = ET.ElementTree(root)
    xml_bytes = ET.tostring(root, encoding="utf-8")
    with gzip.open(output_file, "wb") as f:
        f.write(xml_bytes)
    print(f"Final merged file written: {output_file}")
    print(f"Channels kept: {len(channels)}")
    print(f"Programs kept: {len(programs)}")
    print(f"Approx size: {len(xml_bytes) / 1024 / 1024:.2f} MB")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    merged_channels, merged_programs = merge_feeds(FEEDS)
    write_merged_file(merged_channels, merged_programs, OUTPUT_FILE)

