#!/usr/bin/env python3
import gzip
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib

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
# ARABIC FIX
# =========================
def fix_arabic_channel_id(cid):
    if not cid:
        return cid
    norm_cid = cid.strip().lower()
    if "arabica" in norm_cid:
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
# WRITE OUTPUT
# =========================
def write_output(root, name):
    tree = ET.ElementTree(root)
    xml_file = f"{name}.xml"
    tree.write(xml_file, encoding="utf-8", xml_declaration=True, method="xml")
    with open(xml_file, "rb") as f_in:
        with gzip.open(f"{xml_file}.gz", "wb") as f_out:
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

    merged_root = ET.Element("tv")
    local_root = ET.Element("tv")

    # =========================
    # HASH-BASED DEDUPLICATION
    # =========================
    def programme_hash(p):
        parts = [
            p.attrib.get("channel",""),
            p.attrib.get("start",""),
            p.attrib.get("stop",""),
        ] + [t.text or "" for t in p.findall("title")]
        return hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()

    merged_hashes = set()
    local_hashes = set()

    for cid, ch in all_channels.items():
        merged_root.append(ch)
    for cid, plist in programmes_by_channel.items():
        for p in plist:
            h = programme_hash(p)
            merged_programmes = merged_root.findall("programme")
            local_programmes = local_root.findall("programme")
            if h not in merged_hashes:
                merged_root.append(p)
                merged_hashes.add(h)
            if cid in local_channel_ids and h not in local_hashes:
                local_root.append(p)
                local_hashes.add(h)

    # =========================
    # STATS
    # =========================
    merged_channels = len(all_channels)
    local_channels_count = len(local_channels)
    merged_programmes_count = len(merged_root.findall("programme"))
    local_programmes_count = len(local_root.findall("programme"))

    print("\n--- STATS ---")
    print("merged_channels", merged_channels)
    print("local_channels", local_channels_count)
    print("merged_programmes", merged_programmes_count)
    print("local_programmes", local_programmes_count)
    print("days_kept", DAYS_TO_KEEP)

    # =========================
    # WRITE OUTPUT
    # =========================
    write_output(merged_root, "merged")
    write_output(local_root, "local")
    print("Done")

if __name__ == "__main__":
    main()
