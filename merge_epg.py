import gzip
import os
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

# =========================
# LOAD SOURCES (external file)
# =========================
def load_sources(path="epg_sources.txt"):
    sources = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sources.append(line)
    return sources


# =========================
# LOAD MASTER CHANNEL LIST (STRICT LOCAL FILTER)
# =========================
def load_master(path="master_channels.txt"):
    channels = []
    for line in open(path, "r", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        channels.append(line)
    return channels


# =========================
# NORMALIZATION (SAFE, NOT AGGRESSIVE)
# =========================
def norm(s):
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)        # remove (HD), (US), etc
    s = re.sub(r"[^a-z0-9]+", "", s)     # collapse symbols
    return s.strip()


# =========================
# SMART MATCH (CONTROLLED FUZZY)
# =========================
def is_local_match(channel_name, master_set):
    n = norm(channel_name)

    # exact match
    if n in master_set:
        return True

    # partial token match (SAFE)
    # prevents "cozi tv extra asia india hd 4k" explosions
    for m in master_set:
        if m in n or n in m:
            return True

    return False


# =========================
# FETCH XML (gzip supported)
# =========================
def fetch(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()

    if url.endswith(".gz"):
        import io
        import gzip as gz
        return gz.decompress(r.content)
    return r.content


# =========================
# PARSE XML
# =========================
def parse(xml_bytes):
    return ET.fromstring(xml_bytes)


# =========================
# WRITE OUTPUT (XML + GZ)
# =========================
def write_output(root, name):
    tree = ET.ElementTree(root)

    xml_file = f"{name}.xml"
    tree.write(xml_file, encoding="utf-8", xml_declaration=True)

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

    all_channels = {}
    all_programmes = []

    local_channels = {}
    local_programmes = []

    # =========================
    # PROCESS SOURCES
    # =========================
    for url in sources:
        xml_bytes = fetch(url)
        root = parse(xml_bytes)

        for child in root:
            if child.tag == "channel":
                cid = child.attrib.get("id")
                if cid and cid not in all_channels:
                    all_channels[cid] = child

                    name = "".join(child.itertext())

                    if is_local_match(name, master_set):
                        local_channels[cid] = child

            elif child.tag == "programme":
                cid = child.attrib.get("channel")
                all_programmes.append(child)

                if cid in local_channels:
                    local_programmes.append(child)

    # =========================
    # BUILD MERGED XML
    # =========================
    merged = ET.Element("tv")
    for c in all_channels.values():
        merged.append(c)
    for p in all_programmes:
        merged.append(p)

    # =========================
    # BUILD LOCAL XML
    # =========================
    local = ET.Element("tv")
    for c in local_channels.values():
        local.append(c)
    for p in local_programmes:
        local.append(p)

    # =========================
    # STATS
    # =========================
    print("\n--- STATS ---")
    print("Merged channels:", len(all_channels))
    print("Local channels:", len(local_channels))
    print("Local programmes:", len(local_programmes))

    # =========================
    # OUTPUT
    # =========================
    write_output(merged, "merged")
    write_output(local, "local")

    print("Done")


if __name__ == "__main__":
    main()
