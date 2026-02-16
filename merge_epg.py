import os
import gzip
import shutil
import requests
from datetime import datetime
import pytz
import xml.etree.ElementTree as ET

# --------------------------
# Helper: normalize channel
# --------------------------
def normalize_channel_name(name):
    if not name:
        return None
    name = name.replace(".us2", "").replace(".us_locals1", "")
    name = name.replace(".xml.gz", "")
    name = name.replace("-", " ").replace(".", " ")
    name = name.replace("hd", "").replace("dt", "").replace("tv", "")
    # Skip channels with West/Pacific
    if "west" in name.lower() or "pacific" in name.lower():
        return None
    name = name.strip()
    return name if name else None

# --------------------------
# Fetch EPG and parse channels
# --------------------------
def fetch_and_parse_epg(url):
    print(f"Fetching {url}")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        content = resp.content

        # Handle gzipped XML
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

        # Handle plain TXT or other text files
        elif url.endswith(".txt"):
            return [line.strip() for line in content.decode("utf-8", errors="ignore").splitlines() if line.strip()]

        # Try XML if not gz
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
    not_found_channels = []

    # Process each EPG source
    for url in epg_sources:
        parsed_channels = fetch_and_parse_epg(url)
        print(f"Processed {url} - Parsed {len(parsed_channels)} channels")

        for ch in parsed_channels:
            normalized = normalize_channel_name(ch)
            if not normalized:
                continue

            # Match strictly against master list after normalization
            matched = None
            for master in master_channels:
                master_norm = normalize_channel_name(master)
                if not master_norm:
                    continue
                if normalized.lower() == master_norm.lower() or normalized.lower().startswith(master_norm.lower()):
                    matched = master
                    break

            if matched and matched not in found_channels:
                found_channels.append(matched)
            elif not matched and normalized not in not_found_channels:
                not_found_channels.append(normalized)

    # Create merged file (placeholder, replace with your actual merge logic)
    merged_filename = "merged_epg.xml.gz"
    with gzip.open(merged_filename, "wb") as f:
        f.write(b"<tv></tv>")

    final_file_size = os.path.getsize(merged_filename) / (1024*1024)
    print(f"Final merged file size: {final_file_size:.2f} MB")

    update_index_page(found_channels, not_found_channels, master_channels, final_file_size)

if __name__ == "__main__":
    main()

