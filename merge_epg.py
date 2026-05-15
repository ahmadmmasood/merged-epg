#!/usr/bin/env python3
import gzip
import requests
from lxml import etree
from datetime import datetime, timedelta

EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"

MERGED_XML_FILE = "merged.xml"
LOCAL_XML_FILE = "local.xml"

DAYS_TO_KEEP = 3

# -------------------------
# FETCH + PARSE
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
# MASTER LIST
# -------------------------
def load_master_list():
    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        return [
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


# -------------------------
# CHANNEL HELPERS
# -------------------------
def get_channel_name(channel):
    name = channel.findtext("display-name")
    return (name or "").strip()


def channel_matches_master(channel_name, master_list):
    n = channel_name.lower()
    return any(m in n for m in master_list)


def normalize_channel_id(cid):
    if not cid:
        return ""
    return cid.split(".")[0]


# -------------------------
# PROGRAM FILTERS
# -------------------------
def filter_programs_by_channels(programmes, valid_ids):
    valid = set(valid_ids)
    return [
        p for p in programmes
        if normalize_channel_id(p.get("channel")) in valid
    ]


def filter_programs_by_date(programmes, days):
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days)

    out = []
    for p in programmes:
        start = p.get("start")
        if not start:
            continue
        try:
            dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S")
        except:
            continue

        if dt <= cutoff:
            out.append(p)

    return out


# -------------------------
# MAIN PIPELINE
# -------------------------
def main():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)

    master_list = load_master_list()

    all_channels = {}
    all_programmes = []

    # -------------------------
    # LOAD ALL SOURCES
    # -------------------------
    for url in sources:
        try:
            root = fetch_xml(url)
        except Exception as e:
            print(f"Failed: {url} -> {e}")
            continue

        for ch in root.findall("channel"):
            cid = normalize_channel_id(ch.get("id"))
            ch.set("id", cid)
            all_channels[cid] = ch

        for p in root.findall("programme"):
            p.set("channel", normalize_channel_id(p.get("channel")))
            all_programmes.append(p)

    print(f"Total unique channels: {len(all_channels)}")
    print(f"Total programmes: {len(all_programmes)}")

    # -------------------------
    # FILTER MERGED (MASTER LIST ONLY)
    # -------------------------
    merged_channels = {}
    for cid, ch in all_channels.items():
        name = get_channel_name(ch)
        if channel_matches_master(name, master_list):
            merged_channels[cid] = ch

    merged_ids = set(merged_channels.keys())

    merged_programmes = filter_programs_by_channels(all_programmes, merged_ids)
    merged_programmes = filter_programs_by_date(merged_programmes, DAYS_TO_KEEP)

    # -------------------------
    # WRITE MERGED
    # -------------------------
    merged_root = etree.Element("tv")
    for ch in merged_channels.values():
        merged_root.append(ch)
    for p in merged_programmes:
        merged_root.append(p)

    merged_xml = etree.tostring(merged_root, encoding="utf-8", xml_declaration=True)

    with open(MERGED_XML_FILE, "wb") as f:
        f.write(merged_xml)

    print(f"Saved {MERGED_XML_FILE}")

    # -------------------------
    # FILTER LOCAL (FROM MERGED ONLY)
    # -------------------------
    local_keywords = [
        "wrc", "wttg", "wjla", "wusa", "wdca", "wnuv",
        "wbal", "wmar", "wmpb", "whut", "wdvm",
        "cozi", "comet", "grit", "laff", "quest",
        "antenna", "start tv", "court tv", "roar",
        "metv", "world channel", "pbs kids", "mpt",
        "masn", "nbc sports washington"
    ]

    def is_local(name):
        n = name.lower()
        return any(k in n for k in local_keywords)

    local_channels = {
        cid: ch for cid, ch in merged_channels.items()
        if is_local(get_channel_name(ch))
    }

    local_ids = set(local_channels.keys())
    local_programmes = filter_programs_by_channels(merged_programmes, local_ids)

    # -------------------------
    # WRITE LOCAL
    # -------------------------
    local_root = etree.Element("tv")
    for ch in local_channels.values():
        local_root.append(ch)
    for p in local_programmes:
        local_root.append(p)

    local_xml = etree.tostring(local_root, encoding="utf-8", xml_declaration=True)

    with open(LOCAL_XML_FILE, "wb") as f:
        f.write(local_xml)

    print(f"Saved {LOCAL_XML_FILE}")

    print("\nDone.")
    print(f"Merged channels: {len(merged_channels)}")
    print(f"Local channels: {len(local_channels)}")
    print(f"Local programmes: {len(local_programmes)}")


if __name__ == "__main__":
    main()
