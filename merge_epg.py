import os
import gzip
import shutil
import requests
from datetime import datetime
from xml.etree import ElementTree as ET
import pytz

# ===============================
# Load master list from text file
# ===============================
def load_master_list(filename="master_channels.txt"):
    master_channels = []
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                master_channels.append(line)
    return master_channels

# ===============================
# Normalize channels
# ===============================
def normalize_channel(name):
    if not name:
        return ""
    name = name.lower()
    # remove suffixes
    for suffix in ['.us2', '.us_locals1', '.xml.gz']:
        name = name.replace(suffix, '')
    # replace dots with space
    name = name.replace('.', ' ')
    # remove HD, SD, DT, TV
    for remove_str in [' hd', ' sd', ' dt', ' tv']:
        name = name.replace(remove_str, '')
    # remove Pacific and West
    for remove_str in [' pacific', ' west']:
        name = name.replace(remove_str, '')
    # collapse multiple spaces
    name = ' '.join(name.split())
    return name.strip()

# ===============================
# Fetch and parse EPG
# ===============================
def fetch_and_parse_epg(url):
    print(f"Fetching {url}")
    epg_content = {}
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '')
        data = response.content
        # handle gzipped XML
        if url.endswith('.gz') or 'gzip' in content_type:
            with open("temp.gz", "wb") as f:
                f.write(data)
            with gzip.open("temp.gz", "rb") as f_in, open("temp.xml", "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            tree = ET.parse("temp.xml")
            root = tree.getroot()
            for channel in root.findall('channel'):
                ch_name = channel.get('id') or channel.findtext('display-name')
                if ch_name:
                    epg_content[ch_name] = channel
            os.remove("temp.gz")
            os.remove("temp.xml")
        else:  # handle text-based EPG
            lines = data.decode(errors='ignore').splitlines()
            for line in lines:
                line = line.strip()
                if line:
                    epg_content[line] = None
        print(f"Processed {url} - Parsed {len(epg_content)} channels")
        return epg_content
    except Exception as e:
        print(f"Error fetching/parsing {url}: {e}")
        return {}

# ===============================
# Main merge logic
# ===============================
def main():
    master_channels = load_master_list("master_channels.txt")
    
    # Load EPG sources
    epg_sources = []
    with open("epg_sources.txt", "r") as f:
        epg_sources = [line.strip() for line in f.readlines() if line.strip()]

    all_epg_channels = {}
    for url in epg_sources:
        epg_channels = fetch_and_parse_epg(url)
        all_epg_channels.update(epg_channels)

    # Normalize all parsed EPG channels
    normalized_epg = {normalize_channel(ch): ch for ch in all_epg_channels if normalize_channel(ch)}

    # Matching
    found_channels = {}
    not_found_channels = {}
    for master in master_channels:
        norm_master = normalize_channel(master)
        matched = None
        for epg_norm, original in normalized_epg.items():
            # non-strict contains check
            if norm_master in epg_norm or epg_norm in norm_master:
                matched = original
                break
        if matched:
            found_channels[master] = matched
        else:
            not_found_channels[master] = None

    # Create merged XML
    merged_file = "merged_epg.xml.gz"
    root = ET.Element("tv")
    for ch_name, elem in found_channels.items():
        ET.SubElement(root, "channel", id=ch_name)
    tree = ET.ElementTree(root)
    tree.write("merged_epg.xml")
    with gzip.open(merged_file, "wb") as f_out:
        with open("merged_epg.xml", "rb") as f_in:
            shutil.copyfileobj(f_in, f_out)
    os.remove("merged_epg.xml")

    # Final merged file size
    final_size = os.path.getsize(merged_file) / (1024*1024)

    # Update index.html
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')
    html_content = f"""
<html>
<head><title>EPG Merge Status</title></head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {last_updated}</p>
<p><strong>Total channels in master list:</strong> {len(master_channels)}</p>
<p><strong>Channels found:</strong> {len(found_channels)}</p>
<p><strong>Channels not found:</strong> {len(not_found_channels)}</p>
<p><strong>Final merged file size:</strong> {final_size:.2f} MB</p>

<h2>Channels Found</h2>
<table border="1">
<tr><th>Master List</th><th>Matched EPG Channel</th></tr>
{''.join([f"<tr><td>{m}</td><td>{v}</td></tr>" for m,v in found_channels.items()])}
</table>

<h2>Channels Not Found</h2>
<table border="1">
<tr><th>Master List</th></tr>
{''.join([f"<tr><td>{m}</td></tr>" for m in not_found_channels.keys()])}
</table>
</body>
</html>
"""
    with open("index.html", "w") as f:
        f.write(html_content)

    print("index.html has been updated.")
    print(f"Final merged file size: {final_size:.2f} MB")
    print(f"Channels found: {len(found_channels)}, Channels not found: {len(not_found_channels)}")

if __name__ == "__main__":
    main()

