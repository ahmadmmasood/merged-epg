#!/usr/bin/env python3

import gzip
import requests
from lxml import etree

EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"

MERGED_XML_FILE = "merged.xml"
LOCAL_XML_FILE = "local.xml"


def fetch_xml(url):
    print(f"Fetching {url}")

    r = requests.get(url, timeout=60)
    r.raise_for_status()

    content = r.content

    if url.endswith(".gz"):
        content = gzip.decompress(content)

    return etree.fromstring(content)


# ----------------------------
# MERGED (UNCHANGED BEHAVIOR)
# ----------------------------

def load_master_channels():
    channels = []

    for line in open(MASTER_CHANNELS_FILE, "r", encoding="utf-8"):
        line = line.strip()

        if line and not line.startswith("#"):
            channels.append(line.lower())

    return channels


def filter_channels_loose(channels, master_channels):
    master = set(master_channels)

    matched = []

    for ch in channels:
        name = ch.findtext("display-name", default="").lower()

        if any(m in name for m in master):
            matched.append(ch)

    return matched


def filter_programmes(programmes, allowed_ids):
    allowed = set(allowed_ids)

    return [
        p for p in programmes
        if p.get("channel", "") in allowed
    ]


# ----------------------------
# LOCAL ONLY (STRICT FILTER)
# ----------------------------

def load_local_channels():
    allowed = set()
    capture = False

    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line.startswith("#========================="):
                capture = ("LOCAL CHANNELS" in line)

            elif capture:
                if line and not line.startswith("#"):
                    allowed.add(line.lower())

    return allowed


def filter_local_channels(channels, allowed_names):
    allowed = set(allowed_names)

    matched = []

    for ch in channels:
        name = ch.findtext("display-name", default="").lower()

        if name in allowed:
            matched.append(ch)

    return matched


# ----------------------------
# SAVE
# ----------------------------

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


# ----------------------------
# MAIN
# ----------------------------

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

    print(f"Total channels: {len(all_channels)}")
    print(f"Total programmes: {len(all_programmes)}")

    # ---------------- MERGED OUTPUT (UNCHANGED LOGIC)
    master = load_master_channels()
    merged_channels = filter_channels_loose(all_channels, master)

    merged_ids = [ch.get("id") for ch in merged_channels]

    merged_programmes = filter_programmes(all_programmes, merged_ids)

    merged_root = etree.Element("tv")

    for ch in merged_channels:
        merged_root.append(ch)

    for p in merged_programmes:
        merged_root.append(p)

    save_xml(merged_root, MERGED_XML_FILE)

    # ---------------- LOCAL OUTPUT (STRICT LOCAL ONLY)
    local_allowed = load_local_channels()

    local_channels = filter_local_channels(all_channels, local_allowed)

    local_ids = [ch.get("id") for ch in local_channels]

    local_programmes = filter_programmes(all_programmes, local_ids)

    local_root = etree.Element("tv")

    for ch in local_channels:
        local_root.append(ch)

    for p in local_programmes:
        local_root.append(p)

    save_xml(local_root, LOCAL_XML_FILE)

    print("Done.")


if __name__ == "__main__":
    main()
