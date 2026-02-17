import os
import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

MASTER_LIST_FILE = "master_channels.txt"
OUTPUT_XML_GZ = "merged.xml.gz"
INDEX_HTML = "index.html"

epg_sources = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.txt",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.txt",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
]

def fetch_content(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
        return None

def parse_channels_from_txt(content):
    channels = set()
    for line in content.decode(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        # remove suffixes like .us2, .locals1
        line = line.split('.')[:-1]
        line_name = " ".join(line).replace("HD", "").replace("HDTV", "").replace("Pacific", "").replace("West", "").strip()
        if line_name:
            channels.add(line_name.lower())
    return channels

def parse_channels_from_xml(content):
    channels = set()
    try:
        root = ET.fromstring(content)
        for ch in root.findall("channel"):
            name = ch.attrib.get("id") or ch.findtext("display-name") or ""
            name = name.lower()
            if name:
                channels.add(name)
    except Exception as e:
        print(f"Error parsing XML: {e}")
    return channels

def load_master_list():
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        return set(line.strip().lower() for line in f if line.strip())

def merge_channels(parsed_channel_sets):
    merged = set()
    for s in parsed_channel_sets:
        merged.update(s)
    return merged

def save_merged_xml(merged_channels):
    # create a minimal XML
    root = ET.Element("tv")
    for ch in sorted(merged_channels):
        ch_elem = ET.SubElement(root, "channel", id=ch)
        ET.SubElement(ch_elem, "display-name").text = ch
    tree = ET.ElementTree(root)
    # write XML then gzip it
    tmp_xml = "merged_tmp.xml"
    tree.write(tmp_xml, encoding="utf-8", xml_declaration=True)
    with open(tmp_xml, "rb") as f_in, gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
        f_out.writelines(f_in)
    os.remove(tmp_xml)

def update_index_html(master_channels, found, not_found):
    merged_size = os.path.getsize(OUTPUT_XML_GZ) / (1024*1024)
    found_html = "".join(f"<tr><td>{ch}</td></tr>" for ch in sorted(found))
    not_found_html = "".join(f"<tr><td>{ch}</td></tr>" for ch in sorted(not_found))
    html = f"""
<html>
<head><title>iEPG Merge Report</title></head>
<body>
<h1>iEPG Merge Report</h1>
<p>Total channels in master list: {len(master_channels)}</p>
<p>Channels found: {len(found)} (show/hide)</p>
<p>Channels not found: {len(not_found)} (show/hide)</p>
<p>Final merged file size: {merged_size:.2f} MB</p>

<h2>Found Channels</h2>
<table border="1">{found_html}</table>

<h2>Not Found Channels</h2>
<table border="1">{not_found_html}</table>
</body>
</html>
"""
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    master_channels = load_master_list()
    parsed_sets = []

    for url in epg_sources:
        print(f"Fetching {url}")
        content = fetch_content(url)
        if content is None:
            continue
        if url.endswith(".txt"):
            parsed = parse_channels_from_txt(content)
        else:
            parsed = parse_channels_from_xml(content)
        print(f"Processed {url} - Parsed {len(parsed)} channels")
        parsed_sets.append(parsed)

    merged_channels = merge_channels(parsed_sets)
    save_merged_xml(merged_channels)

    found = set(ch for ch in master_channels if ch in merged_channels)
    not_found = master_channels - found

    update_index_html(master_channels, found, not_found)
    print("index.html has been updated.")
    print(f"Final merged file size: {os.path.getsize(OUTPUT_XML_GZ)/(1024*1024):.2f} MB")

if __name__ == "__main__":
    main()

