import gzip
import re
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta

# =========================
# CONFIG (CHANGE THIS ONLY)
# =========================
DAYS_TO_KEEP = 3  # 👈 change to 7, 5, 14 etc if needed

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
    # XMLTV format: 20260116120000 +0000
    return datetime.strptime(s[:14], "%Y%m%d%H%M%S")


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

    channel_versions = defaultdict(list)
    programmes_by_channel = defaultdict(list)

    now = datetime.utcnow()
    cutoff = now + timedelta(days=DAYS_TO_KEEP)

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
                if cid:
                    channel_versions[cid].append(child)

            # ---------------------
            # PROGRAMMES (3-DAY FILTER APPLIED HERE)
            # ---------------------
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

    # =========================
    # SELECT BEST CHANNEL VERSION
    # =========================
    all_channels = {}

    for cid, versions in channel_versions.items():
        best = max(versions, key=lambda c: len(c.findall("display-name")))
        all_channels[cid] = best

    # =========================
    # LOCAL MATCHING (STABLE VERSION)
    # =========================
    local_channels = {}
    local_channel_ids = set()

    for cid, ch in all_channels.items():
        name = " ".join(t for t in ch.itertext() if t and t.strip()).strip()
        name_norm = norm(name)

        # stable safe match
        if any(
            name_norm == norm(m) or
            name_norm.startswith(norm(m) + " ") or
            name_norm.endswith(" " + norm(m))
            for m in master_set
        ):
            local_channels[cid] = ch
            local_channel_ids.add(cid)

    # =========================
    # BUILD PROGRAMMES
    # =========================
    merged_programmes = []
    local_programmes = []

    for cid, plist in programmes_by_channel.items():
        merged_programmes.extend(plist)

        if cid in local_channel_ids:
            local_programmes.extend(plist)

    # =========================
    # BUILD XML ROOTS
    # =========================
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

    # =========================
    # STATS
    # =========================
    print("\n--- STATS ---")
    print("merged_channels", len(all_channels))
    print("local_channels", len(local_channels))
    print("merged_programmes", len(merged_programmes))
    print("local_programmes", len(local_programmes))
    print("days_kept", DAYS_TO_KEEP)

    # =========================
    # OUTPUT
    # =========================
    write_output(merged_root, "merged")
    write_output(local_root, "local")

    print("Done")


if __name__ == "__main__":
    main()
