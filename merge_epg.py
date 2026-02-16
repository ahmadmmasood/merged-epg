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
    # Lowercase
    name = name.lower()
    # Remove suffixes like .us2, .locals1
    name = name.replace(".us2", "").replace(".locals1", "")
    # Replace "." with spaces
    name = name.replace(".", " ")
    # Remove HD/HDTV, Pacific/West
    for token in ["hd", "hdtv", "pacific", "west"]:
        name = name.replace(token, "")
    # Strip extra whitespace
    name = " ".join(name.split())
    return name

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
        table {{ border-collapse: collapse; width: 50%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
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

    # Here you would merge the actual XMLs and create 'merged_epg.xml.gz'
    # (This part is unchanged from your existing code)
    # Example placeholder:
    if not os.path.exists("merged_epg.xml.gz"):
        with gzip.open("merged_epg.xml.gz", "wb") as f:
            f.write(b"<epg></epg>")  # Replace with actual merged content

    update_index_page(master_channels, list(found_channels_set))

if __name__ == "__main__":
    main()

