#!/usr/bin/env python3

import gzip
import requests
from lxml import etree
from datetime import datetime, timedelta, timezone

EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"

MERGED_XML_FILE = "merged.xml"
LOCAL_XML_FILE = "local.xml"

# Keep only X days of guide data
# Set to None to disable filtering
DAYS_TO_KEEP = 3

# contains = partial match
# exact = exact match
LOCAL_MATCH_MODE = "contains"


def fetch_xml(url):
    print(f"Fetching: {url}")

    response = requests.get(url, timeout=60)
    response.raise_for_status()

    content = response.content

    if url.endswith(".gz"):
        content = gzip.decompress(content)

    parser = etree.XMLParser(recover=True, huge_tree=True)

    return etree.fromstring(content, parser=parser)


def load_master_channels():
    channels = []

    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            channels.append(line.lower())

    return channels


def normalize_channel_id(channel_id):
    """
    Converts:
    WJLA-DT.us_locals1 -> WJLA-DT
    """

    if not channel_id:
        return ""

    return channel_id.split(".")[0].strip()


def filter_local_channels(channels, master_channels):
    matched = []

    for ch in channels:

        channel_id = ch.get("id", "")
        normalized_id = normalize_channel_id(channel_id).lower()

        display_name = ch.findtext("display-name", default="")
        display_name = display_name.lower()

        for master in master_channels:

            if LOCAL_MATCH_MODE == "contains":

                if (
                    master in normalized_id
                    or master in display_name
                ):
                    matched.append(ch)
                    break

            elif LOCAL_MATCH_MODE == "exact":

                if (
                    master == normalized_id
                    or master == display_name
                ):
                    matched.append(ch)
                    break

    return matched


def filter_programmes_by_channels(programmes, allowed_ids):
    allowed = set(allowed_ids)

    filtered = []

    for prog in programmes:

        channel_id = prog.get("channel", "")

        normalized = normalize_channel_id(channel_id)

        if normalized in allowed:
            filtered.append(prog)

    return filtered


def filter_programmes_by_days(programmes, days):

    if days is None:
        return programmes

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)

    filtered = []

    for prog in programmes:

        start = prog.get("start")

        if not start:
            continue

        try:
            # XMLTV format:
            # 20260514050600 +0000

            dt = datetime.strptime(
                start[:14],
                "%Y%m%d%H%M%S"
            ).replace(tzinfo=timezone.utc)

        except Exception:
            continue

        if now <= dt <= cutoff:
            filtered.append(prog)

    return filtered


def remove_duplicate_channels(channels):

    unique = {}

    for ch in channels:

        normalized = normalize_channel_id(
            ch.get("id", "")
        )

        if normalized not in unique:

            ch.set("id", normalized)

            unique[normalized] = ch

    return list(unique.values())


def normalize_programme_channels(programmes):

    for prog in programmes:

        original = prog.get("channel", "")

        prog.set(
            "channel",
            normalize_channel_id(original)
        )

    return programmes


def save_xml(root, filename):

    xml_data = etree.tostring(
        root,
        encoding="utf-8",
        pretty_print=True,
        xml_declaration=True
    )

    with open(filename, "wb") as f:
        f.write(xml_data)

    with gzip.open(filename + ".gz", "wb") as gz:
        gz.write(xml_data)

    print(f"Saved: {filename}")
    print(f"Saved: {filename}.gz")


def main():

    print("Loading source list...")

    sources = []

    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            sources.append(line)

    all_channels = []
    all_programmes = []

    for url in sources:

        try:

            root = fetch_xml(url)

            channels = root.findall("channel")
            programmes = root.findall("programme")

            print(f"Channels found: {len(channels)}")
            print(f"Programmes found: {len(programmes)}")

            all_channels.extend(channels)
            all_programmes.extend(programmes)

        except Exception as e:

            print(f"FAILED: {url}")
            print(str(e))

    print()
    print(f"Total raw channels: {len(all_channels)}")
    print(f"Total raw programmes: {len(all_programmes)}")

    # Normalize IDs
    all_channels = remove_duplicate_channels(all_channels)
    all_programmes = normalize_programme_channels(all_programmes)

    print(f"Unique channels after normalization: {len(all_channels)}")

    # Filter by days
    all_programmes = filter_programmes_by_days(
        all_programmes,
        DAYS_TO_KEEP
    )

    print(f"Programmes after date filtering: {len(all_programmes)}")

    # Build merged XML
    merged_root = etree.Element("tv")

    for ch in all_channels:
        merged_root.append(ch)

    for prog in all_programmes:
        merged_root.append(prog)

    save_xml(merged_root, MERGED_XML_FILE)

    # Load desired local channels
    master_channels = load_master_channels()

    # Match channels
    local_channels = filter_local_channels(
        all_channels,
        master_channels
    )

    local_ids = [
        normalize_channel_id(ch.get("id", ""))
        for ch in local_channels
    ]

    print()
    print("Matched local channels:")

    for cid in sorted(local_ids):
        print(f" - {cid}")

    # Filter programmes
    local_programmes = filter_programmes_by_channels(
        all_programmes,
        local_ids
    )

    print(f"Local programmes kept: {len(local_programmes)}")

    # Build local XML
    local_root = etree.Element("tv")

    for ch in local_channels:
        local_root.append(ch)

    for prog in local_programmes:
        local_root.append(prog)

    save_xml(local_root, LOCAL_XML_FILE)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
