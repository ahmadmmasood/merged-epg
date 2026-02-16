import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime

# ---------------- Sources ----------------
sources = [
    # Local US feeds with text files (preferable over XML for speed)
    "https://epgshare01.online/epgshare01/epg_ripper_US2.txt",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.txt",
    
    # Foreign feeds with XML files (fallback when text files not available)
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

# ---------------- Channel Criteria ----------------
local_channels = [
    "WRC-HD", "COZI", "CRIMES", "Oxygen", "WTTG-DT", "BUZZR", "START", "WJLA", "Charge!", "Comet",
    "ROAR", "WUSA-HD", "Crime", "Quest", "NEST", "QVC", "WBAL-DT", "MeTV", "Story", "GetTV", "QVC",
    "WFDC-DT", "getTV", "GRIT", "UniMas", "WDCA", "MOVIES", "HEROES", "FOXWX", "MPT-HD", "MPT-2", "MPTKIDS",
    "NHK-WLD", "WDVM-SD", "WETA-HD", "WETA UK", "KIDS", "WORLD", "METRO", "WHUT", "PBSKids", "WZDC", "XITOS",
    "WDCW-DT", "Antenna", "CWWNUV", "Comet", "TheNest", "ION", "Bounce", "CourtTV", "Laff", "IONPlus",
    "BUSTED", "GameSho", "HSN", "AltaVsn", "DEFY"
]

# ---------------- Variables ----------------
all_channels = {}
all_programs = {}

# ---------------- Index Page Update ----------------
def update_index_page(timestamp, channels_count, programs_count, file_size_mb, logs):
    index_path = "index.html"
    try:
        with open(index_path, "w") as index_file:
            index_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>EPG Merge Status</title>
                <meta charset="UTF-8">
            </head>
            <body>
                <h1>EPG Merge Status</h1>
                <p><strong>Last updated:</strong> {timestamp}</p>
                <p><strong>Channels kept:</strong> {channels_count}</p>
                <p><strong>Programs kept:</strong> {programs_count}</p>
                <p><strong>Final merged file size:</strong> {file_size_mb} MB</p>
                <details>
                    <summary>Logs</summary>
                    <pre>{logs}</pre>
                </details>
            </body>
            </html>
            """
            index_file.write(index_content)
    except Exception as e:
        print(f"Error writing to index.html: {e}")

# ---------------- Fetch Channels from Text Files ----------------
def fetch_and_parse_txt(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text.strip().splitlines()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

# ---------------- Build Final XML ----------------
def build_final_xml(channels_all, programs_all):
    root = ET.Element("tv")
    for ch_id, ch_name in channels_all:
        channel_element = ET.SubElement(root, "channel", id=ch_id)
        ET.SubElement(channel_element, "display-name").text = ch_name

    for pr_id, program in programs_all.items():
        program_element = ET.SubElement(root, "programme", channel=pr_id)
        ET.SubElement(program_element, "title").text = program

    final_xml = ET.tostring(root, encoding="utf-8", method="xml")
    return final_xml

# ---------------- Main Process ----------------
def process_feeds():
    channels_all = []
    programs_all = {}

    # Process all source URLs
    logs = []
    for url in sources:
        if url.endswith(".txt"):
            channels = fetch_and_parse_txt(url)
            for ch in channels:
                ch_name = ch.strip()
                if any(local_channel in ch_name for local_channel in local_channels):
                    # Filtering to keep only the local channels
                    channels_all.append((ch_name, ch_name))  # Simulating channel ID as name for now
                    logs.append(f"Processing TXT: {url} - {ch_name}")
        elif url.endswith(".xml.gz"):
            try:
                response = requests.get(url)
                response.raise_for_status()
                with gzip.open(response.content, 'rb') as f:
                    content = f.read()
                    tree = ET.ElementTree(ET.fromstring(content))
                    root = tree.getroot()

                    # Process channels
                    for ch in root.findall("channel"):
                        ch_id = ch.get("id")
                        ch_name = ch.find("display-name").text.strip() if ch.find("display-name") is not None else None
                        if ch_name and ch_name not in channels_all:
                            channels_all.append((ch_id, ch_name))
                    
                    # Process programs
                    for pr in root.findall("programme"):
                        pr_id = pr.get("channel")
                        title = pr.find("title").text.strip() if pr.find("title") else None
                        if pr_id and title:
                            programs_all[f"{pr_id}_{title}"] = title
                    logs.append(f"Processing XML: {url}")
            except Exception as e:
                logs.append(f"Error processing XML: {url} - {e}")

    # Build final XML
    final_xml = build_final_xml(channels_all, programs_all)

    # Compress to .gz file
    with gzip.open("merged.xml.gz", "wb") as f:
        f.write(final_xml)

    # Update index page with timestamp and counts
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    file_size_mb = round(len(final_xml) / (1024 * 1024), 2)
    update_index_page(timestamp, len(channels_all), len(programs_all), file_size_mb, "\n".join(logs))

if __name__ == "__main__":
    process_feeds()

