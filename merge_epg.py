#!/usr/bin/env python3
import gzip
import requests
from lxml import etree
from datetime import datetime, timedelta
import pytz

EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"
MERGED_XML_FILE = "merged.xml"
LOCAL_XML_FILE = "local.xml"
DAYS_TO_KEEP = 3  # optional, keeps N days of programming
LOCAL_MATCH_MODE = "contains"  # "contains" partial matching

def fetch_xml(url):
    print(f"Fetching {url} ...")
    r = requests.get(url)
    r.raise_for_status()
    content = r.content
    if url.endswith(".gz"):
        content = gzip.decompress(content)
    return etree.fromstring(content)

def load_master_channels():
    channels = []
    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                channels.append(line.lower())
    return channels

def normalize_channel_id(channel_id):
    """Remove suffix after dot, e.g., WJLA-DT.us_locals1 -> WJLA-DT"""
    return channel_id.split(".")[0]

def filter_local_channels(channels, master_channels):
    matched = []
    for ch in channels:
        ch_name = ch.get("display-name") or ch.findtext("display-name")
        if ch_name:
            ch_name_lower = ch_name.lower()
            for m in master_channels:
                if LOCAL_MATCH_MODE == "contains" and m in ch_name_lower:
                    matched.append(ch)
                    break
    return matched

def filter_programs_by_channels(programmes, channel_ids):
    channel_set = set(channel_ids)
    return [p for p in programmes if normalize_channel_id(p.get("channel", "")) in channel_set]

def filter_programs_by_days(programmes, days):
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    cutoff = now + timedelta(days=days)
    filtered = []
    for p in programmes:
        start_str = p.get("start")
        if not start_str:
            continue
        # Format: 20260507033500 +0000
        try:
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=pytz.UTC)
        except:
            continue
        if start_dt <= cutoff:
            filtered.append(p)
    return filtered

def main():
    print("Loading EPG sources...")
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)

    all_channels = []
    all_programmes = []

    for url in sources:
        try:
            xml_root = fetch_xml(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue

        channels = xml_root.findall("channel")
        programmes = xml_root.findall("programme")

        # Normalize channel IDs
        for ch in channels:
            orig_id = ch.get("id")
            ch.set("id", normalize_channel_id(orig_id))

        for p in programmes:
            p.set("channel", normalize_channel_id(p.get("channel", "")))

        all_channels.extend(channels)
        all_programmes.extend(programmes)

    print(f"Total channels fetched: {len(all_channels)}")
    print(f"Total programmes fetched: {len(all_programmes)}")

    # Remove duplicate channels by ID
    unique_channels = {}
    for ch in all_channels:
        unique_channels[ch.get("id")] = ch
    all_channels = list(unique_channels.values())

    # Filter programs by optional DAYS_TO_KEEP
    if DAYS_TO_KEEP:
        all_programmes = filter_programs_by_days(all_programmes, DAYS_TO_KEEP)

    # Save merged XML
    merged_root = etree.Element("tv")
    for ch in all_channels:
        merged_root.append(ch)
    for p in all_programmes:
        merged_root.append(p)

    merged_xml_str = etree.tostring(merged_root, encoding="utf-8", xml_declaration=True)
    with open(MERGED_XML_FILE, "wb") as f:
        f.write(merged_xml_str)
    with gzip.open(MERGED_XML_FILE + ".gz", "wb") as f:
        f.write(merged_xml_str)
    print(f"Saved merged XML ({MERGED_XML_FILE}, {MERGED_XML_FILE}.gz)")

    # Load master channels for local filtering
    master_channels = load_master_channels()

    # Filter local channels
    local_channels = filter_local_channels(all_channels, master_channels)
    local_channel_ids = [ch.get("id") for ch in local_channels]
    local_programmes = filter_programs_by_channels(all_programmes, local_channel_ids)

    print(f"Local channels matched: {[ch.get('id') for ch in local_channels]}")
    print(f"Local programmes included: {len(local_programmes)}")

    # Save local XML
    local_root = etree.Element("tv")
    for ch in local_channels:
        local_root.append(ch)
    for p in local_programmes:
        local_root.append(p)

    local_xml_str = etree.tostring(local_root, encoding="utf-8", xml_declaration=True)
    with open(LOCAL_XML_FILE, "wb") as f:
        f.write(local_xml_str)
    with gzip.open(LOCAL_XML_FILE + ".gz", "wb") as f:
        f.write(local_xml_str)
    print(f"Saved local XML ({LOCAL_XML_FILE}, {LOCAL_XML_FILE}.gz)")

if __name__ == "__main__":
    main()
