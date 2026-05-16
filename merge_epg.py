import gzip
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

# =========================
# LOAD FILES
# =========================

def load_sources(path="epg_sources.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def load_master(path="master_channels.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


# =========================
# NORMALIZATION (STRICT + SAFE)
# =========================

def norm(s):
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[._\-]+", " ", s)
    tokens = re.findall(r"[a-z0-9]+", s)
    return " ".join(tokens).strip()


# =========================
# FETCH
# =========================

def fetch(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def parse(xml_bytes):
    return ET.fromstring(xml_bytes)


# =========================
# CHANNEL EXTRACTION
# =========================

def extract_channel_keys(channel):
    keys = []

    cid = channel.attrib.get("id", "")
    if cid:
        keys.append(cid)

    for dn in channel.findall("display-name"):
        if dn.text:
            keys.append(dn.text)

    return keys


# =========================
# MASTER SET
# =========================

def build_master_set(master_list):
    return set(norm(x) for x in master_list)


# =========================
# MATCH (NO FUZZY GUESSING)
# =========================

def is_in_master(channel, master_set):
    for key in extract_channel_keys(channel):
        n = norm(key)
        if n and n in master_set:
            return True
    return False


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
    master_set = build_master_set(master)

    # -------------------------
    # IMPORTANT FIX:
    # store ALL channel versions
    # -------------------------
    channel_versions = defaultdict(list)
    programmes = []

    for url in sources:
        xml_bytes = fetch(url)
        root = parse(xml_bytes)

        for child in root:

            if child.tag == "channel":
                cid = child.attrib.get("id")
                if cid:
                    channel_versions[cid].append(child)

            elif child.tag == "programme":
                programmes.append(child)

    # -------------------------
    # MERGE CHANNELS PROPERLY
    # -------------------------
    merged_channels = {}

    for cid, versions in channel_versions.items():

        # pick richest version (most display-name tags)
        best = max(
            versions,
            key=lambda x: len(x.findall("display-name"))
        )

        merged_channels[cid] = best

    # -------------------------
    # BUILD OUTPUTS
    # -------------------------

    merged_root = ET.Element("tv")
    local_root = ET.Element("tv")

    local_channel_ids = set()

    # ALL channels in merged output
    for c in merged_channels.values():
        merged_root.append(c)

    # LOCAL subset (STRICT master match)
    for cid, c in merged_channels.items():
        if is_in_master(c, master_set):
            local_root.append(c)
            local_channel_ids.add(cid)

    # PROGRAMMES
    merged_prog = []
    local_prog = []

    for p in programmes:
        cid = p.attrib.get("channel")

        merged_prog.append(p)

        if cid in local_channel_ids:
            local_prog.append(p)

    for p in merged_prog:
        merged_root.append(p)

    for p in local_prog:
        local_root.append(p)

    # -------------------------
    # STATS
    # -------------------------
    print("\n--- STATS ---")
    print("Merged channels:", len(merged_channels))
    print("Local channels:", len(local_channel_ids))
    print("Merged programmes:", len(merged_prog))
    print("Local programmes:", len(local_prog))

    # -------------------------
    # OUTPUT
    # -------------------------
    write_output(merged_root, "merged")
    write_output(local_root, "local")

    print("Done")


if __name__ == "__main__":
    main()
