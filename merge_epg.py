#!/usr/bin/env python3
import gzip
import requests
from lxml import etree

EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"

MERGED_XML_FILE = "merged.xml"
LOCAL_XML_FILE = "local.xml"

# -------------------------
# LOAD MASTER LIST
# -------------------------
def load_master_list():
    tiers = []
    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                tiers.append(line.lower())
    return tiers

# -------------------------
# FETCH XML
# -------------------------
def fetch_xml(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    data = r.content
    if url.endswith(".gz"):
        data = gzip.decompress(data)

    return etree.fromstring(data)

# -------------------------
# CHANNEL NAME
# -------------------------
def channel_name(ch):
    return (ch.findtext("display-name") or "").strip()

# -------------------------
# MATCH LOGIC (SIMPLE)
# -------------------------
def matches(name, master_list):
    n = name.lower()
    return any(m in n for m in master_list)

# -------------------------
# MAIN
# -------------------------
def main():
    master_list = load_master_list()

    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        sources = [x.strip() for x in f if x.strip() and not x.startswith("#")]

    all_channels = []
    all_programmes = []

    # -------------------------
    # LOAD ALL SOURCES
    # -------------------------
    for url in sources:
        try:
            root = fetch_xml(url)
        except Exception as e:
            print(f"FAILED {url}: {e}")
            continue

        all_channels.extend(root.findall("channel"))
        all_programmes.extend(root.findall("programme"))

    print(f"TOTAL CHANNELS: {len(all_channels)}")
    print(f"TOTAL PROGRAMMES: {len(all_programmes)}")

    # -------------------------
    # FILTER CHANNELS (MASTER LIST ONLY)
    # -------------------------
    selected_channels = []
    selected_ids = set()

    for ch in all_channels:
        name = channel_name(ch)

        if name and matches(name, master_list):
            selected_channels.append(ch)
            cid = ch.get("id")
            if cid:
                selected_ids.add(cid)

    print(f"SELECTED CHANNELS: {len(selected_channels)}")

    # -------------------------
    # FILTER PROGRAMMES (STRICT ID MATCH)
    # -------------------------
    selected_programmes = [
        p for p in all_programmes
        if p.get("channel") in selected_ids
    ]

    print(f"SELECTED PROGRAMMES: {len(selected_programmes)}")

    # -------------------------
    # WRITE MERGED XML
    # -------------------------
    merged_root = etree.Element("tv")

    for ch in selected_channels:
        merged_root.append(ch)

    for p in selected_programmes:
        merged_root.append(p)

    merged_data = etree.tostring(
        merged_root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True
    )

    with open(MERGED_XML_FILE, "wb") as f:
        f.write(merged_data)

    with gzip.open(MERGED_XML_FILE + ".gz", "wb") as f:
        f.write(merged_data)

    # -------------------------
    # LOCAL = ONLY LOCAL SECTION
    # -------------------------
    local_keywords = [
        "wrc", "wttg", "wjla", "wusa", "wdca", "wnuv",
        "wbal", "wmar", "wmpb", "wfdc", "wdvm", "weta", "whut",
        "comet", "charge", "grit", "quest", "antenna", "laff",
        "start tv", "buzzr", "mpt", "world channel"
    ]

    def is_local(name):
        n = name.lower()
        return any(k in n for k in local_keywords)

    local_channels = []
    local_ids = set()

    for ch in all_channels:
        name = channel_name(ch)

        if name and is_local(name):
            local_channels.append(ch)
            cid = ch.get("id")
            if cid:
                local_ids.add(cid)

    local_programmes = [
        p for p in all_programmes
        if p.get("channel") in local_ids
    ]

    print(f"LOCAL CHANNELS: {len(local_channels)}")
    print(f"LOCAL PROGRAMMES: {len(local_programmes)}")

    # -------------------------
    # WRITE LOCAL XML
    # -------------------------
    local_root = etree.Element("tv")

    for ch in local_channels:
        local_root.append(ch)

    for p in local_programmes:
        local_root.append(p)

    local_data = etree.tostring(
        local_root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True
    )

    with open(LOCAL_XML_FILE, "wb") as f:
        f.write(local_data)

    with gzip.open(LOCAL_XML_FILE + ".gz", "wb") as f:
        f.write(local_data)

    print("DONE")

if __name__ == "__main__":
    main()
