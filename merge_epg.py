import os
import gzip
import pytz
import requests
from datetime import datetime
from xml.etree import ElementTree as ET

# -----------------------------
# NORMALIZATION FUNCTION
# -----------------------------
def normalize_channel_name(name):
    if not name:
        return None
    name = name.lower()
    # Remove suffixes like .us_locals1, .us2, etc.
    for suffix in [".us_locals1", ".us2"]:
        name = name.replace(suffix, "")
    # Replace dots with spaces
    name = name.replace(".", " ")
    # Remove -dt, HD/HDTV, Pacific/West
    for token in ["-dt", "hd", "hdtv", "pacific", "west"]:
        name = name.replace(token, "")
    # Trim spaces
    name = " ".join(name.split())

    # Map known local variations to master list
    local_map = {
        "wrc": "wrc-hd", "cozi": "cozi tv", "crimes": "crimes", "oxygen": "oxygen",
        "wttg": "wttg-dt", "buzzr": "buzzr", "start": "start tv", "wjla": "wjla",
        "charge": "charge!", "comet": "comet", "roar": "roar", "wusa": "wusa-hd",
        "crime": "crime tv", "quest": "quest", "the nest": "the nest", "qvc": "qvc",
        "wbal": "wbal-dt", "metv": "metv", "story television": "story television",
        "gettv": "gettv", "wfdc": "wfdc-dt", "grit": "grit", "unimas": "unimas",
        "wdca": "wdca", "movies": "movies!", "heroes & icons": "heroes & icons",
        "fox weather": "fox weather", "mpt": "mpt-hd", "mpt-2": "mpt-2",
        "mpt kids": "mpt kids", "nhk world japan": "nhk world japan", "wdvm": "wdvm-sd",
        "weta": "weta-hd", "weta uk": "weta uk", "weta kids": "weta kids",
        "world channel": "world channel", "metro": "metro", "whut": "whut",
        "pbs kids": "pbs kids", "wzdc": "wzdc", "xitos": "xitos", "wdcw": "wdcw-dt",
        "antenna": "antenna tv", "cwwnuv": "cwwnuv", "bounce": "bounce",
        "court tv": "court tv", "laff": "laff", "busted": "busted",
        "hsn": "hsn", "altavsn": "altavsn", "defy": "defy"
    }
    return local_map.get(name, name)

# -----------------------------
# FETCH AND PARSE EPG
# -----------------------------
def fetch_and_parse_epg(url):
    try:
        print(f"Fetching {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.content

        # Handle TXT files
        if url.endswith(".txt"):
            lines = content.decode("utf-8", errors="ignore").splitlines()
            channels = [normalize_channel_name(line.strip()) for line in lines if line.strip()]
            return [c for c in channels if c]

        # Handle XML/GZ
        if url.endswith(".gz"):
            content = gzip.decompress(content)
        tree = ET.ElementTree(ET.fromstring(content))
        channels = [normalize_channel_name(ch.find("display-name").text) 
                    for ch in tree.findall(".//channel") if ch.find("display-name") is not None]
        return [c for c in channels if c]

    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return []

# -----------------------------
# LOAD MASTER LIST
# -----------------------------
def load_master_channels(file_path):
    with open(file_path, "r") as f:
        channels = f.readlines()
    channels = [line.strip() for line in channels if line.strip() and not line.startswith("#")]
    channels = [normalize_channel_name(c) for c in channels]
    return channels

# -----------------------------
# UPDATE INDEX.HTML
# -----------------------------
def update_index_page(master_channels, found_channels):
    not_found_channels = [c for c in master_channels if c not in found_channels]
    merged_file_size = os.path.getsize("merged_epg.xml.gz") / (1024*1024) if os.path.exists("merged_epg.xml.gz") else 0

    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

    html_content = f"""
<html>
<head>
    <title>EPG Merge Status</title>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #fafafa; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; max-width: 700px; margin-bottom: 20px; font-size: 14px; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr.found {{ background-color: #d4edda; }}
        tr.notfound {{ background-color: #f8d7da; }}
    </style>
</head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {last_updated}</p>
<p><strong>Total channels in master list:</strong> {len(master_channels)}</p>
<p><strong>Channels found:</strong> {len(found_channels)}</p>
<p><strong>Channels not found:</strong> {len(not_found_channels)}</p>
<p><strong>Final merged file size:</strong> {merged_file_size:.2f} MB</p>

<h2>Channels Found</h2>
<table>
<tr><th>Channel Name</th></tr>
{''.join([f'<tr class="found"><td>{c}</td></tr>' for c in found_channels])}
</table>

<h2>Channels Not Found</h2>
<table>
<tr><th>Channel Name</th></tr>
{''.join([f'<tr class="notfound"><td>{c}</td></tr>' for c in not_found_channels])}
</table>
</body>
</html>
"""
    with open("index.html", "w") as f:
        f.write(html_content)
    print("index.html updated.")

# -----------------------------
# MAIN MERGE FUNCTION
# -----------------------------
def main():
    master_channels = load_master_channels("master_channels.txt")
    epg_sources = []
    with open("epg_sources.txt", "r") as f:
        epg_sources = [line.strip() for line in f if line.strip()]

    found_channels_set = set()

    for url in epg_sources:
        parsed_channels = fetch_and_parse_epg(url)
        print(f"Processed {url} - Parsed {len(parsed_channels)} channels")
        for c in parsed_channels:
            if c in master_channels:
                found_channels_set.add(c)

    # Create merged XML file placeholder if not exists
    if not os.path.exists("merged_epg.xml.gz"):
        with gzip.open("merged_epg.xml.gz", "wb") as f:
            f.write(b"<epg></epg>")  # Replace with actual merged XML content

    # Update index.html with counts and final file size
    update_index_page(master_channels, list(found_channels_set))

if __name__ == "__main__":
    main()

