#!/usr/bin/env python3

import gzip
import requests
from lxml import etree

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
# LOAD MASTER FILE
# -------------------------

def load_master_keywords():
    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        return [
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


# -------------------------
# LOAD LOCAL SECTION
# -------------------------

def load_local_keywords():
    keywords = set()
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
                    keywords.add(line.lower())

    return keywords


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
# LOCAL FILTER (SAFE MATCH)
# -------------------------

def is_local_channel(ch, keywords):
    name = ch.findtext("display-name", default="").lower()
    cid = ch.get("id", "").lower()

    base_id = cid.split(".")[0]

    for k in keywords:
        if k in name or k in base_id:
            return True

    return False


def build_local_channels(all_channels, keywords):
    return [
        ch for ch in all_channels
        if is_local_channel(ch, keywords)
    ]


# -------------------------
# PROGRAMME FILTER
# -------------------------

def filter_programmes(programmes, allowed_ids):
    allowed = set(allowed_ids)

    return [
        p for p in programmes
        if p.get("channel", "").lower().split(".")[0] in allowed
    ]


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
    local_keywords = load_local_keywords()

    print("\n--- LOCAL DEBUG START ---")
    print("LOCAL KEYWORDS COUNT:", len(local_keywords))
    print("SAMPLE KEYWORDS:", list(local_keywords)[:20])

    local_channels = build_local_channels(all_channels, local_keywords)

    print("\nLOCAL CHANNELS FOUND:", len(local_channels))

    print("\nSAMPLE LOCAL CHANNELS:")
    for ch in local_channels[:10]:
        print(" -", ch.get("id"), "|", ch.findtext("display-name"))

    local_ids = [ch.get("id", "") for ch in local_channels]

    local_programmes = [
        p for p in all_programmes
        if p.get("channel", "").lower().split(".")[0] in local_ids
    ]

    print("\nLOCAL PROGRAMMES FOUND:", len(local_programmes))

    if len(local_channels) == 0:
        print("\n❌ WARNING: LOCAL CHANNELS = 0 (nothing will appear in local.xml)")

        print("\nCHECK FIRST FEW FEED CHANNEL IDs:")
        for ch in all_channels[:20]:
            print(" -", ch.get("id"), "|", ch.findtext("display-name"))

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
