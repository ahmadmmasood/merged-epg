#!/usr/bin/env python3

import gzip
import requests
from lxml import etree
import re

EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"

MERGED_XML_FILE = "merged.xml"
LOCAL_XML_FILE = "local.xml"


# -------------------------
# FETCH XML
# -------------------------

def fetch_xml(url):
    print(f"Fetching {url}")

    r = requests.get(url, timeout=60)
    r.raise_for_status()

    content = r.content

    if url.endswith(".gz"):
        content = gzip.decompress(content)

    return etree.fromstring(content)


# -------------------------
# NORMALIZE (FAST)
# -------------------------

def normalize(text):
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# -------------------------
# LOAD MASTER
# -------------------------

def load_master_keywords():
    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        return [
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


# -------------------------
# LOAD LOCAL LIST
# -------------------------

def load_local_list():
    items = set()
    capture = False

    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if "LOCAL CHANNELS" in line:
                capture = True
                continue

            if capture:
                if line.startswith("#================"):
                    continue
                if line and not line.startswith("#"):
                    items.add(line)

    return items


# -------------------------
# MERGED FILTER
# -------------------------

def filter_merged_channels(channels, keywords):
    keywords = set(keywords)

    return [
        ch for ch in channels
        if any(k in ch.findtext("display-name", default="").lower() for k in keywords)
    ]


# -------------------------
# FAST PROGRAMME FILTER (FIXED)
# -------------------------

def filter_programmes(programmes, allowed_ids):
    """
    KEY FIX:
    - NO fuzzy matching
    - NO 'any()'
    - NO repeated normalization loops
    - single-pass hash lookup
    """

    allowed = set(allowed_ids)

    result = []

    for p in programmes:
        cid = normalize(p.get("channel", ""))

        if cid in allowed:
            result.append(p)

    return result


# -------------------------
# SAVE XML
# -------------------------

def save_xml(root, filename):
    data = etree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True
    )

    with open(filename, "wb") as f:
        f.write(data)

    with gzip.open(filename + ".gz", "wb") as f:
        f.write(data)

    print(f"Saved {filename}")


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

    for url in sources:
        root = fetch_xml(url)

        all_channels.extend(root.findall("channel"))
        all_programmes.extend(root.findall("programme"))

    print(f"\nTotal channels: {len(all_channels)}")
    print(f"Total programmes: {len(all_programmes)}")

    # ---------------- MERGED ----------------
    master_keywords = load_master_keywords()

    merged_channels = filter_merged_channels(all_channels, master_keywords)

    merged_ids = [ch.get("id", "") for ch in merged_channels]

    merged_programmes = filter_programmes(all_programmes, merged_ids)

    merged_root = etree.Element("tv")

    for ch in merged_channels:
        merged_root.append(ch)

    for p in merged_programmes:
        merged_root.append(p)

    save_xml(merged_root, MERGED_XML_FILE)

    # ---------------- LOCAL ----------------
    local_raw = load_local_list()

    local_allowed = set(normalize(x) for x in local_raw)

    print("\n--- LOCAL DEBUG ---")
    print("LOCAL ITEMS:", len(local_allowed))
    print("SAMPLE:", list(local_allowed)[:20])

    local_channels = [
        ch for ch in all_channels
        if normalize(ch.get("id", "")) in local_allowed
        or normalize(ch.findtext("display-name", "")) in local_allowed
    ]

    local_programmes = filter_programmes(all_programmes, local_allowed)

    print("\nLOCAL CHANNELS FOUND:", len(local_channels))
    print("LOCAL PROGRAMMES FOUND:", len(local_programmes))

    # ---------------- SAVE LOCAL ----------------
    local_root = etree.Element("tv")

    for ch in local_channels:
        local_root.append(ch)

    for p in local_programmes:
        local_root.append(p)

    save_xml(local_root, LOCAL_XML_FILE)

    print("\nDone.")


if __name__ == "__main__":
    main()
