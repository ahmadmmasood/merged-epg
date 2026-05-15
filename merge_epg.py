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
    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        return [
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


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
# HELPERS
# -------------------------
def display_name(ch):
    return (ch.findtext("display-name") or "").strip()


def matches_local(name, master_list):
    n = name.lower()
    return any(m in n for m in master_list)


# -------------------------
# MAIN
# -------------------------
def main():
    master_list = load_master_list()

    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        sources = [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

    all_channels = {}
    all_programmes = {}

    # -------------------------
    # LOAD SOURCES
    # -------------------------
    for url in sources:
        try:
            root = fetch_xml(url)
        except Exception as e:
            print(f"FAILED {url}: {e}")
            continue

        # CHANNELS (dedupe by id)
        for ch in root.findall("channel"):
            cid = ch.get("id")
            if cid and cid not in all_channels:
                all_channels[cid] = ch

        # PROGRAMMES (dedupe by composite key)
        for p in root.findall("programme"):
            key = (
                p.get("channel"),
                p.get("start"),
                (p.findtext("title") or "").strip()
            )
            if key not in all_programmes:
                all_programmes[key] = p

    print(f"TOTAL UNIQUE CHANNELS: {len(all_channels)}")
    print(f"TOTAL UNIQUE PROGRAMMES: {len(all_programmes)}")

    # -------------------------
    # BUILD MERGED XML
    # -------------------------
    merged_root = etree.Element("tv")

    for ch in all_channels.values():
        merged_root.append(ch)

    for p in all_programmes.values():
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

    print("Saved merged.xml")


    # -------------------------
    # LOCAL FILTER (MASTER LIST ONLY)
    # -------------------------
    local_channels = {}
    local_programmes = {}

    for cid, ch in all_channels.items():
        name = display_name(ch)

        if name and matches_local(name, master_list):
            local_channels[cid] = ch

    local_ids = set(local_channels.keys())

    for p in all_programmes.values():
        if p.get("channel") in local_ids:
            key = (
                p.get("channel"),
                p.get("start"),
                (p.findtext("title") or "").strip()
            )
            if key not in local_programmes:
                local_programmes[key] = p

    print(f"LOCAL CHANNELS: {len(local_channels)}")
    print(f"LOCAL PROGRAMMES: {len(local_programmes)}")

    # -------------------------
    # WRITE LOCAL XML
    # -------------------------
    local_root = etree.Element("tv")

    for ch in local_channels.values():
        local_root.append(ch)

    for p in local_programmes.values():
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

    print("Saved local.xml")
    print("Done")


if __name__ == "__main__":
    main()
