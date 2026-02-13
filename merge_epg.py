#!/usr/bin/env python3
import gzip
import requests
from lxml import etree
import sys
from io import BytesIO

# ------------------------------
# Configuration: EPG sources
# ------------------------------
EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://raw.githubusercontent.com/MuazT/EPG-Guide/master/ArabicEPG.xml",
    "https://raw.githubusercontent.com/MuazT/EPG-Guide/master/TurkishEPG.xml"
]

# List of missing channels to include from ALL_SOURCES
MISSING_CHANNELS = [
    "ahgani tv", "arabica tv", "balle balle", "jalwa 9x", "love nature",
    "nagoumfmtb", "mbc masr", "mbc masr2", "mbc1", "b4u", "Al.Aghani.ae"
]

# List of premium channels to preserve (East Coast)
PREMIUM_CHANNELS = [
    "hbo", "max", "showtime", "starz", "a&e", "hgtv", "amc", "comedy central"
]

# US timezones to filter for East Coast
EAST_COAST_TIMEZONES = ["EST", "EDT"]


# ------------------------------
# Functions
# ------------------------------

def download_xml(url):
    print(f"Downloading {url} ...")
    response = requests.get(url)
    response.raise_for_status()
    content = response.content
    # decompress if gz
    if url.endswith(".gz"):
        with gzip.GzipFile(fileobj=BytesIO(content)) as f:
            return f.read()
    else:
        return content

def parse_xml(content):
    return etree.fromstring(content)

def filter_us_east(xml_root):
    # keep channels in East Coast only for US channels
    for channel in xml_root.xpath("//channel"):
        tz = channel.get("timezone", "").upper()
        if "US" in tz and tz not in EAST_COAST_TIMEZONES:
            parent = channel.getparent()
            parent.remove(channel)
    return xml_root

def merge_roots(roots):
    merged_root = etree.Element("tv")
    for root in roots:
        for elem in root:
            merged_root.append(elem)
    return merged_root

def preserve_missing_channels(xml_root):
    # Keep only the channels in missing list and premium channels
    for channel in xml_root.xpath("//channel"):
        name = channel.get("display-name", "").lower()
        if any(m.lower() in name for m in MISSING_CHANNELS + PREMIUM_CHANNELS):
            continue
        # For US channels, keep East Coast only
        tz = channel.get("timezone", "").upper()
        if "US" in tz and tz not in EAST_COAST_TIMEZONES:
            parent = channel.getparent()
            parent.remove(channel)
    return xml_root

# ------------------------------
# Main
# ------------------------------

def main(output_path):
    roots = []
    for url in EPG_SOURCES:
        try:
            content = download_xml(url)
            root = parse_xml(content)
            roots.append(root)
        except Exception as e:
            print(f"Failed to process {url}: {e}")

    merged_root = merge_roots(roots)
    merged_root = preserve_missing_channels(merged_root)

    # Write output gzipped
    tree = etree.ElementTree(merged_root)
    with gzip.open(output_path, "wb") as f:
        tree.write(f, encoding="UTF-8", xml_declaration=True)
    print(f"Saved merged XML.GZ to {output_path}")


# ------------------------------
# Run
# ------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python merge_epg.py <output_path/merged.xml.gz>")
        sys.exit(1)
    output_file = sys.argv[1]
    main(output_file)

