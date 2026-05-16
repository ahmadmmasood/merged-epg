import gzip
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict
import json

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
    s = re.sub(r"[._\-+/]+", " ", s)

    junk = ["hd", "uhd", "4k", "east", "west", "us", "usa", "channel", "network", "feed"]

    words = re.findall(r"[a-z0-9]+", s)
    words = [w for w in words if w not in junk]

    return " ".join(words)


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
    tree.write(f"{name}.xml", encoding="utf-8", xml_declaration=True)

    with open(f"{name}.xml", "rb") as f_in:
        with gzip.open(f"{name}.xml.gz", "wb") as f_out:
            f_out.write(f_in.read())


# =========================
# MAIN
# =========================
def main():
    sources = load_sources()
    master = load_master()
    master_set = set(norm(x) for x in master)

    channel_versions = defaultdict(list)
    channel_alias = {}

    programmes = []

    # =========================
    # PROCESS SOURCES
    # =========================
    for url in sources:
        xml_bytes = fetch(url)
        root = parse(xml_bytes)

        for child in root:

            if child.tag == "channel":
                cid = child.attrib.get("id")
                if not cid:
                    continue

                channel_versions[cid].append(child)

                for dn in child.findall("display-name"):
                    if dn.text:
                        channel_alias[norm(dn.text)] = cid

            elif child.tag == "programme":
                programmes.append(child)

    # =========================
    # BEST CHANNEL VERSION
    # =========================
    all_channels = {}

    for cid, versions in channel_versions.items():
        all_channels[cid] = max(versions, key=lambda c: len(c.findall("display-name")))

    # =========================
    # LOCAL FILTER
    # =========================
    local_channels = {}
    local_channel_ids = set()

    for cid, ch in all_channels.items():
        for dn in ch.findall("display-name"):
            if dn.text and norm(dn.text) in master_set:
                local_channels[cid] = ch
                local_channel_ids.add(cid)
                break

    # =========================
    # PROGRAMMES
    # =========================
    all_programmes = []
    local_programmes = []

    for p in programmes:
        raw = p.attrib.get("channel")
        if not raw:
            continue

        cid = channel_alias.get(norm(raw))
        if not cid:
            continue

        # rewrite channel ID (IMPORTANT FIX)
        p.attrib["channel"] = cid

        all_programmes.append(p)

        if cid in local_channel_ids:
            local_programmes.append(p)

    # =========================
    # OUTPUT XML
    # =========================
    merged = ET.Element("tv")
    for c in all_channels.values():
        merged.append(c)
    for p in all_programmes:
        merged.append(p)

    local = ET.Element("tv")
    for c in local_channels.values():
        local.append(c)
    for p in local_programmes:
        local.append(p)

    # =========================
    # STATS
    # =========================
    stats = {
        "merged_channels": len(all_channels),
        "local_channels": len(local_channels),
        "merged_programmes": len(all_programmes),
        "local_programmes": len(local_programmes),
    }

    with open("stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    with open("log.txt", "w") as f:
        for k, v in stats.items():
            f.write(f"{k}: {v}\n")

    print("\n--- STATS ---")
    for k, v in stats.items():
        print(k, v)

    # =========================
    # WRITE OUTPUT
    # =========================
    write_output(merged, "merged")
    write_output(local, "local")


if __name__ == "__main__":
    main()
