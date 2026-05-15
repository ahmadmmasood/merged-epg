#!/usr/bin/env python3

import gzip
import requests
from lxml import etree
from collections import defaultdict

EPG_SOURCES_FILE = "epg_sources.txt"
MERGED_XML_FILE = "merged.xml"
LOCAL_XML_FILE = "local.xml"


# -------------------------
# NORMALIZE CHANNEL ID
# -------------------------
def norm_id(x):
    return (x or "").lower().split(".")[0].split(" ")[0].strip()


# -------------------------
# FETCH XML
# -------------------------
def fetch_xml(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=90)
    r.raise_for_status()

    content = r.content
    if url.endswith(".gz"):
        content = gzip.decompress(content)

    return etree.fromstring(content)


# -------------------------
# LOCAL WHITELIST (STRICT OTA ONLY)
# -------------------------
LOCAL_CHANNELS = {
    "wrc-dt",
    "wttg-dt",
    "wjla-dt",
    "wusa-dt",
    "wdcw-dt",
    "wdca-dt",
    "wzdc-dt",
    "wfdc-dt",
    "whut-dt",
    "weta-dt",

    "wbal-dt",
    "wjz-dt",
    "wmar-dt",
    "wnuv-dt",
    "wbff-dt",
    "wutb-dt",
    "wmpb-dt",
    "wmpt-dt"
}


def is_local(cid):
    return norm_id(cid) in LOCAL_CHANNELS


# -------------------------
# MAIN
# -------------------------
def main():

    sources = [
        line.strip()
        for line in open(EPG_SOURCES_FILE, "r", encoding="utf-8")
        if line.strip() and not line.startswith("#")
    ]

    all_channels = []
    all_programmes = []

    # -------------------------
    # FETCH ALL SOURCES
    # -------------------------
    for url in sources:
        try:
            root = fetch_xml(url)

            all_channels.extend(root.findall("channel"))
            all_programmes.extend(root.findall("programme"))

        except Exception as e:
            print(f"Failed: {url} -> {e}")

    print(f"\nTotal channels: {len(all_channels)}")
    print(f"Total programmes: {len(all_programmes)}")


    # -------------------------
    # DEDUP CHANNELS (MERGED FIX)
    # -------------------------
    seen = set()
    unique_channels = []

    for c in all_channels:
        cid = norm_id(c.get("id"))

        if cid in seen:
            continue

        seen.add(cid)
        c.set("id", cid)
        unique_channels.append(c)

    all_channels = unique_channels


    # -------------------------
    # INDEX PROGRAMMES (FAST LOOKUP)
    # -------------------------
    program_index = defaultdict(list)

    for p in all_programmes:
        cid = norm_id(p.get("channel"))
        program_index[cid].append(p)


    # -------------------------
    # BUILD MERGED XML
    # -------------------------
    merged_root = etree.Element("tv")

    for c in all_channels:
        merged_root.append(c)

    for cid, progs in program_index.items():
        for p in progs:
            merged_root.append(p)

    merged_xml = etree.tostring(
        merged_root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True
    )

    with open(MERGED_XML_FILE, "wb") as f:
        f.write(merged_xml)

    with gzip.open(MERGED_XML_FILE + ".gz", "wb") as f:
        f.write(merged_xml)

    print(f"Saved {MERGED_XML_FILE}")


    # -------------------------
    # LOCAL FILTER (STRICT)
    # -------------------------
    local_channels = [
        c for c in all_channels
        if is_local(c.get("id"))
    ]

    local_ids = {c.get("id") for c in local_channels}

    local_programmes = [
        p for p in all_programmes
        if norm_id(p.get("channel")) in local_ids
    ]

    print("\n--- LOCAL DEBUG ---")
    print("LOCAL CHANNELS FOUND:", len(local_channels))
    print("LOCAL PROGRAMMES FOUND:", len(local_programmes))


    # -------------------------
    # BUILD LOCAL XML
    # -------------------------
    local_root = etree.Element("tv")

    for c in local_channels:
        local_root.append(c)

    for p in local_programmes:
        local_root.append(p)

    local_xml = etree.tostring(
        local_root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True
    )

    with open(LOCAL_XML_FILE, "wb") as f:
        f.write(local_xml)

    with gzip.open(LOCAL_XML_FILE + ".gz", "wb") as f:
        f.write(local_xml)

    print(f"Saved {LOCAL_XML_FILE}")
    print("\nDone.")


if __name__ == "__main__":
    main()
