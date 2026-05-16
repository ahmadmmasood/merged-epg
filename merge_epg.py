#!/usr/bin/env python3
import gzip
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
import json
import zlib
import os

# =========================
# CONFIG
# =========================
DAYS_TO_KEEP = 3

# =========================
# LOAD SOURCES
# =========================
def load_sources(path="epg_sources.txt"):
    sources = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)
    return sources

# =========================
# LOAD MASTER
# =========================
def load_master(path="master_channels.txt"):
    channels = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                channels.append(line)
    return channels

# =========================
# NORMALIZE
# =========================
def norm(s):
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[._\-]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return " ".join(s.split())

# =========================
# TIME PARSER
# =========================
def parse_time(s):
    return datetime.strptime(s[:14], "%Y%m%d%H%M%S")

# =========================
# ARABIC FIX LAYER
# =========================
def fix_arabic_channel_id(cid):
    if not cid:
        return cid
    if "arabica" in cid.lower():
        return "network.arabica"
    return cid

# =========================
# FETCH
# =========================
def fetch(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.content
    if url.endswith(".gz"):
        return gzip.decompress(data)
    return data

# =========================
# PARSE
# =========================
def parse(xml_bytes):
    return ET.fromstring(xml_bytes)

# =========================
# FAST DUPLICATE REMOVAL
# =========================
def remove_duplicate_programmes_fast(programmes):
    seen = set()
    unique_programmes = []
    for p in programmes:
        channel = p.attrib.get("channel")
        start = p.attrib.get("start")
        stop = p.attrib.get("stop")
        title = p.findtext("title") or ""
        key_bytes = f"{channel}|{start}|{stop}|{title}".encode("utf-8")
        key_hash = zlib.crc32(key_bytes)
        if key_hash not in seen:
            seen.add(key_hash)
            unique_programmes.append(p)
    return unique_programmes

# =========================
# WRITE OUTPUT
# =========================
def write_output(root, name):
    tree = ET.ElementTree(root)
    xml_file = f"{name}.xml"

    if name == "merged":
        programmes = root.findall("programme")
        channels_with_programmes = set(p.attrib.get("channel") for p in programmes)
        for c in list(root.findall("channel")):
            if c.attrib.get("id") not in channels_with_programmes:
                root.remove(c)
        # Remove duplicates safely (fast)
        programmes = root.findall("programme")
        unique_programmes = remove_duplicate_programmes_fast(programmes)
        for p in programmes:
            root.remove(p)
        for p in unique_programmes:
            root.append(p)

    # Strip whitespace
    for elem in root.iter():
        if elem.text:
            elem.text = elem.text.strip()
        if elem.tail:
            elem.tail = elem.tail.strip()

    tree.write(xml_file, encoding="utf-8", xml_declaration=True, method="xml")

    with open(xml_file, "rb") as f_in:
        with gzip.open(f"{xml_file}.gz", "wb", compresslevel=9) as f_out:
            f_out.write(f_in.read())

# =========================
# MAIN
# =========================
def main():
    sources = load_sources()
    master = load_master()
    master_set = set(norm(x) for x in master)

    channel_versions = defaultdict(list)
    programmes_by_channel = defaultdict(list)

    now = datetime.utcnow()
    cutoff = now + timedelta(days=DAYS_TO_KEEP)

    for url in sources:
        xml_bytes = fetch(url)
        root = parse(xml_bytes)
        is_arabic_feed = "ArabicEPG.xml" in url

        for child in root:
            if child.tag == "channel":
                cid = child.attrib.get("id")
                if is_arabic_feed:
                    cid = fix_arabic_channel_id(cid)
                if cid:
                    channel_versions[cid].append(child)
            elif child.tag == "programme":
                cid = child.attrib.get("channel")
                if is_arabic_feed:
                    cid = fix_arabic_channel_id(cid)
                if not cid:
                    continue
                start = child.attrib.get("start")
                if start:
                    try:
                        t = parse_time(start)
                        if t <= cutoff:
                            programmes_by_channel[cid].append(child)
                    except:
                        programmes_by_channel[cid].append(child)
                else:
                    programmes_by_channel[cid].append(child)

    all_channels = {}
    for cid, versions in channel_versions.items():
        best = max(versions, key=lambda c: len(c.findall("display-name")))
        all_channels[cid] = best

    local_channels = {}
    local_channel_ids = set()
    for cid, ch in all_channels.items():
        name = " ".join(t for t in ch.itertext() if t and t.strip()).strip()
        name_norm = norm(name)
        if any(
            name_norm == norm(m) or
            name_norm.startswith(norm(m) + " ") or
            name_norm.endswith(" " + norm(m))
            for m in master_set
        ):
            local_channels[cid] = ch
            local_channel_ids.add(cid)

    merged_programmes = []
    local_programmes = []

    for cid, plist in programmes_by_channel.items():
        merged_programmes.extend(plist)
        if cid in local_channel_ids:
            local_programmes.extend(plist)

    merged_root = ET.Element("tv")
    local_root = ET.Element("tv")

    for c in all_channels.values():
        merged_root.append(c)
    for p in merged_programmes:
        merged_root.append(p)

    for c in local_channels.values():
        local_root.append(c)
    for p in local_programmes:
        local_root.append(p)

    # --- Stats AFTER duplicate removal ---
    merged_programmes_count = len(remove_duplicate_programmes_fast(merged_root.findall("programme")))
    local_programmes_count = len(local_root.findall("programme"))

    # File sizes
    merged_xml_size = os.path.getsize("merged.xml") if os.path.exists("merged.xml") else 0
    merged_gz_size = os.path.getsize("merged.xml.gz") if os.path.exists("merged.xml.gz") else 0
    local_xml_size = os.path.getsize("local.xml") if os.path.exists("local.xml") else 0
    local_gz_size = os.path.getsize("local.xml.gz") if os.path.exists("local.xml.gz") else 0

    print("\n--- STATS ---")
    print("merged_channels", len(all_channels))
    print("local_channels", len(local_channels))
    print("merged_programmes", merged_programmes_count)
    print("local_programmes", local_programmes_count)
    print("days_kept", DAYS_TO_KEEP)
    print("merged_xml_size", merged_xml_size)
    print("merged_gz_size", merged_gz_size)
    print("local_xml_size", local_xml_size)
    print("local_gz_size", local_gz_size)
    print("Done")

    # Write stats.json for dashboard
    stats = {
        "merged_channels": len(all_channels),
        "local_channels": len(local_channels),
        "merged_programmes": merged_programmes_count,
        "local_programmes": local_programmes_count,
        "days_kept": DAYS_TO_KEEP,
        "merged_xml_size": merged_xml_size,
        "merged_gz_size": merged_gz_size,
        "local_xml_size": local_xml_size,
        "local_gz_size": local_gz_size
    }

    with open("stats.json", "w") as f:
        json.dump(stats, f)

    write_output(merged_root, "merged")
    write_output(local_root, "local")

if __name__ == "__main__":
    main()
