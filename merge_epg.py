import gzip
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

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
# FETCH (FIXED GZIP)
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

    # store ALL channel versions (important fix)
    channel_versions = defaultdict(list)

    # alias map for programme linking (critical fix)
    channel_alias = {}

    programmes = []

    # =========================
    # PROCESS SOURCES
    # =========================
    for url in sources:
        xml_bytes = fetch(url)
        root = parse(xml_bytes)

        for child in root:

            # ---------------------
            # CHANNELS
            # ---------------------
            if child.tag == "channel":
                cid = child.attrib.get("id")
                if not cid:
                    continue

                channel_versions[cid].append(child)

                # build alias map
                keys = set()
                keys.add(cid)

                for dn in child.findall("display-name"):
                    if dn.text:
                        keys.add(norm(dn.text))

                for k in keys:
                    channel_alias[norm(k)] = cid

            # ---------------------
            # PROGRAMMES
            # ---------------------
            elif child.tag == "programme":
                programmes.append(child)

    # =========================
    # SELECT BEST CHANNEL VERSION
    # =========================
    all_channels = {}

    for cid, versions in channel_versions.items():
        best = max(versions, key=lambda c: len(c.findall("display-name")))
        all_channels[cid] = best

    # =========================
    # BUILD LOCAL SUBSET
    # =========================
    local_channels = {}
    local_channel_ids = set()

    for cid, ch in all_channels.items():
        name = " ".join(t for t in ch.itertext() if t and t.strip()).strip()

        if norm(name) in master_set:
            local_channels[cid] = ch
            local_channel_ids.add(cid)

    # =========================
    # ASSIGN PROGRAMMES
    # =========================
    all_programmes = []
    local_programmes = []

    for p in programmes:
        raw = p.attrib.get("channel")

        cid = channel_alias.get(norm(raw), raw)

        all_programmes.append(p)

        if cid in local_channel_ids:
            local_programmes.append(p)

    # =========================
    # BUILD OUTPUT XML
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
