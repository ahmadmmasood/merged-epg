import gzip
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
import os
import hashlib

#=========================
# CONFIG
#=========================
DAYS_TO_KEEP = 1

#=========================
# CACHE
#=========================
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_path(url):
    safe = re.sub(r'[^a-zA-Z0-9]', '_', url)
    return os.path.join(CACHE_DIR, f"{safe}.xml")

def hash_path(cache_file):
    return cache_file + ".hash"

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def is_valid_xml(xml_bytes):
    if not xml_bytes or len(xml_bytes) < 100:
        return False
    try:
        root = ET.fromstring(xml_bytes)
        return root.tag == "tv"
    except:
        return False

#=========================
# HELPERS
#=========================
def load_sources(path="epg_sources.txt"):
    sources = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)
    return sources

def load_master(path="master_channels.txt"):
    channels = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                channels.append(line)
    return channels

def norm(s):
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[._\-]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return " ".join(s.split())

def parse_time(s):
    return datetime.strptime(s[:14], "%Y%m%d%H%M%S")

def fetch(url):
    print(f"Fetching {url}")

    r = requests.get(url, timeout=60)
    r.raise_for_status()

    data = r.content

    print(f"Downloaded {len(data)} bytes from {url}")

    if not data:
        raise ValueError("Empty response")

    if url.endswith(".gz"):
        data = gzip.decompress(data)
        print(f"Decompressed size: {len(data)} bytes")

    return data

def parse(xml_bytes):
    if not xml_bytes:
        raise ValueError("Empty XML")
    return ET.fromstring(xml_bytes)

def remove_empty_elements(elem):
    for child in list(elem):
        remove_empty_elements(child)
        if (not child.text or not child.text.strip()) and len(child) == 0:
            elem.remove(child)

def remove_empty_attributes(elem):
    for attr in list(elem.attrib):
        if not elem.attrib[attr].strip():
            del elem.attrib[attr]

def write_output(root, name):
    tree = ET.ElementTree(root)
    xml_file = f"{name}.xml"

    if name == "merged":
        programmes = [p for p in root.findall("programme")]
        channels_with_programmes = set(p.attrib.get("channel") for p in programmes)
        for c in list(root.findall("channel")):
            if c.attrib.get("id") not in channels_with_programmes:
                root.remove(c)

    for elem in root.iter():
        if elem.text:
            elem.text = elem.text.strip()
        if elem.tail:
            elem.tail = elem.tail.strip()

    remove_empty_elements(root)
    for elem in root.iter():
        remove_empty_attributes(elem)

    tree.write(xml_file, encoding="utf-8", xml_declaration=True, method="xml")

    with open(xml_file, "rb") as f_in:
        with gzip.open(f"{xml_file}.gz", "wb", compresslevel=9) as f_out:
            f_out.write(f_in.read())

    return (
        os.path.getsize(xml_file),
        os.path.getsize(f"{xml_file}.gz")
    )

#=========================
# MAIN
#=========================
def main():
    sources = load_sources()
    master = load_master()
    master_set = set(norm(x) for x in master)

    channel_versions = defaultdict(list)
    programmes_by_channel = defaultdict(list)

    now = datetime.utcnow()
    cutoff = now + timedelta(days=DAYS_TO_KEEP)

    for url in sources:
        if "ArabicEPG.xml" in url:
            print(f"Skipping Arabica feed: {url}")
            continue

        cache_file = cache_path(url)
        hfile = hash_path(cache_file)

        xml_bytes = None
        root = None
        used_cache = False

        try:
            xml_bytes = fetch(url)

            if not is_valid_xml(xml_bytes):
                raise ValueError("Fetched XML invalid")

            new_hash = sha256(xml_bytes)

            old_hash = None
            if os.path.exists(hfile):
                with open(hfile, "r") as f:
                    old_hash = f.read().strip()

            # Only update cache if changed
            if new_hash != old_hash:
                with open(cache_file, "wb") as f:
                    f.write(xml_bytes)

                with open(hfile, "w") as f:
                    f.write(new_hash)
            else:
                print(f"[SKIP CACHE UPDATE] No change: {url}")

            root = parse(xml_bytes)

        except Exception as e:
            print("\n==================== FEED FAILED ====================")
            print(f"FAILED FEED: {url}")
            print(f"ERROR: {e}")
            print("TRYING CACHE")
            print("=====================================================\n")

            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "rb") as f:
                        xml_bytes = f.read()

                    if not is_valid_xml(xml_bytes):
                        raise ValueError("Cached XML invalid")

                    root = parse(xml_bytes)
                    used_cache = True

                except Exception as ce:
                    print(f"Cache also invalid: {ce}")
                    continue
            else:
                print("No cache available, skipping")
                continue

        if used_cache:
            print(f"Using cached version: {url}")

        for child in root:
            if child.tag == "channel":
                cid = child.attrib.get("id")
                if cid:
                    channel_versions[cid].append(child)

            elif child.tag == "programme":
                cid = child.attrib.get("channel")
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
        seen = set()
        unique = []

        for p in plist:
            key = (p.attrib.get("channel"), p.attrib.get("start"), p.attrib.get("stop"))
            if key not in seen:
                unique.append(p)
                seen.add(key)

        merged_programmes.extend(unique)

        if cid in local_channel_ids:
            local_programmes.extend(unique)

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

    merged_xml_size, merged_gz_size = write_output(merged_root, "merged")
    local_xml_size, local_gz_size = write_output(local_root, "local")

    print("\n--- STATS ---")
    print("merged_channels", len(all_channels))
    print("local_channels", len(local_channels))
    print("merged_programmes", len(merged_programmes))
    print("local_programmes", len(local_programmes))
    print("days_kept", DAYS_TO_KEEP)
    print(f"merged_xml_size {merged_xml_size // (1024*1024)}M")
    print(f"merged_gz_size {merged_gz_size // (1024*1024)}M")
    print(f"local_xml_size {local_xml_size // (1024*1024)}M")
    print(f"local_gz_size {local_gz_size // (1024*1024)}M")
    print("Done.")

if __name__ == "__main__":
    main()
