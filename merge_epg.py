import os
import gzip
import shutil
import requests
from datetime import datetime
import pytz
import xml.etree.ElementTree as ET
import re

# --------------------------
# Helper: normalize channel
# --------------------------
def normalize_channel_name(name):
    if not name:
        return None
    # remove suffixes
    name = re.sub(r'\.(us2|us_locals1|xml\.gz)$', '', name, flags=re.I)
    # replace dots and symbols
    name = name.replace(".", " ").replace("-", " ").replace("(", " ").replace(")", " ")
    # remove HD, SD, DT, TV, Pacific/West
    name = re.sub(r'\b(HD|SD|DT|TV|pacific|west)\b', '', name, flags=re.I)
    # remove extra symbols + / :
    name = re.sub(r'[^\w\s]', '', name)
    name = name.lower().strip()
    # reduce multiple spaces to one
    name = re.sub(r'\s+', ' ', name)
    return name if name else None

# --------------------------
# Fetch EPG and parse channels
# --------------------------
def fetch_and_parse_epg(url):
    try:
        print(f"Fetching {url}")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        content = resp.content

        if url.endswith(".gz"):
            temp_gz = "temp_epg.gz"
            with open(temp_gz, "wb") as f:
                f.write(content)
            with gzip.open(temp_gz, "rb") as f_in, open("temp_epg.xml", "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            tree = ET.parse("temp_epg.xml")
            root = tree.getroot()
            channels = [ch.findtext("display-name") for ch in root.findall(".//channel") if ch.findtext("display-name")]
            os.remove(temp_gz)
            os.remove("temp_epg.xml")
            return channels

        elif url.endswith(".txt"):
            return [line.strip() for line in content.decode("utf-8", errors="ignore").splitlines() if line.strip()]

        else:
            tree = ET.ElementTree(ET.fromstring(content))
            root = tree.getroot()
            return [ch.findtext("display-name") for ch in root.findall(".//channel") if ch.findtext("display-name")]

    except Exception as e:
        print(f"Error fetching/parsing {url}: {e}")
        return []

# --------------------------
# Load master channels
# --------------------------
def load_master_channels(file_path):
    with open(file_path, "r") as f:
        channels = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return channels

# --------------------------
# Update index.html
# --------------------------
def update_index_page(found_channels, not_found_channels, master_channels, final_file_size):
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>EPG Merge Status</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
h1, h2 {{ margin-bottom: 5px; }}
p {{ margin: 2px 0; }}
table {{ border-collapse: collapse; width: 100%; max-width: 700px; font-size: 14px; }}
th, td {{ border: 1px solid #ccc; padding: 5px; text-align: left; }}
th {{ background-color: #f2f2f2; }}
button {{ margin: 5px 0; padding: 5px 10px; }}
.container {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {last_updated}</p>
<p><strong>Total channels in master list:</strong> {len(master_channels)}</p>
<p><strong>Channels found:</strong> {len(found_channels)}</p>
<p><strong>Channels not found:</strong> {len(not_found_channels)}</p>
<p><strong>Final merged file size:</strong> {final_file_size:.2f} MB</p>

<div class="container">
<h2>Channels Found</h2>
<button onclick="document.getElementById('found').style.display='block'">Show Found</button>
<button onclick="document.getElementById('found').style.display='none'">Hide Found</button>
<div id="found" style="display:none;">
<table>
<tr><th>Channel Name</th></tr>
{''.join([f"<tr><td>{c}</td></tr>" for c in found_channels])}
</table>
</div>
</div>

<div class="container">
<h2>Channels Not Found</h2>
<button onclick="document.getElementById('notfound').style.display='block'">Show Not Found</button>
<button onclick="document.getElementById('notfound').style.display='none'">Hide Not Found</button>
<div id="notfound" style="display:none;">
<table>
<tr><th>Channel Name</th></tr>
{''.join([f"<tr><td>{c}</td></tr>" for c in not_found_channels])}
</table>
</div>
</div>

</body>
</html>
"""
    with open("index.html", "w") as f:
        f.write(html_content)
    print("index.html updated")

# --------------------------
# Main
# --------------------------
def main():
    master_channels = load_master_channels("master_channels.txt")
    print(f"Loaded {len(master_channels)} master channels.")

    epg_sources = []
    with open("epg_sources.txt", "r") as f:
        epg_sources = [line.strip() for line in f if line.strip()]

    found_channels = []

    for url in epg_sources:
        parsed_channels = fetch_and_parse_epg(url)
        print(f"Processed {url} - Parsed {len(parsed_channels)} channels")

        for ch in parsed_channels:
            normalized_ch = normalize_channel_name(ch)
            if not normalized_ch:
                continue

            # flexible matching: either contains or is contained
            for master in master_channels:
                normalized_master = normalize_channel_name(master)
                if not normalized_master:
                    continue
                if (normalized_master in normalized_ch) or (normalized_ch in normalized_master):
                    if master not in found_channels:
                        found_channels.append(master)
                    break

    not_found_channels = [ch for ch in master_channels if ch not in found_channels]

    merged_file_path = "merged_epg.xml.gz"
    final_file_size = os.path.getsize(merged_file_path) / (1024*1024) if os.path.exists(merged_file_path) else 0.0

    print(f"Final merged file size: {final_file_size:.2f} MB")
    update_index_page(found_channels, not_found_channels, master_channels, final_file_size)

if __name__ == "__main__":
    main()

