import os
import gzip
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
    for suffix in ['.us2', '.us_locals1', '.xml.gz']:
        name = name.replace(suffix, '')
    name = name.replace('.', ' ')
    for remove_str in [' hd', ' sd', ' dt', ' tv']:
        name = name.replace(remove_str, '')
    for remove_str in [' pacific', ' west', ' east']:
        name = name.replace(remove_str, '')
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
        data = response.content

        if url.endswith('.gz') or b'gzip' in response.headers.get('Content-Type', ''):
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
                xml_bytes = f.read()
            root = ET.fromstring(xml_bytes)
            for channel in root.findall('channel'):
                ch_name = channel.get('id') or channel.findtext('display-name')
                if ch_name:
                    epg_content[ch_name] = channel
        else:  # text-based EPG
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
    with open("epg_sources.txt", "r") as f:
        epg_sources = [line.strip() for line in f.readlines() if line.strip()]

    all_epg_channels = {}
    for url in epg_sources:
        epg_channels = fetch_and_parse_epg(url)
        all_epg_channels.update(epg_channels)

    normalized_epg = {normalize_channel(ch): ch for ch in all_epg_channels if normalize_channel(ch)}

    # Tricky channels for contains matching
    tricky_channels = [
        "ThrillerMax","MovieMax","5StarMax","OuterMax","Showtime Family Zone","A&E",
        "Cartoonito","HGTV","ION Plus","MTV Live","Nick at Nite","NickMusic","TeenNick",
        "Smithsonian Channel","WRC-HD","WUSA-HD","Heroes & Icons","MPT-HD","MPT-2",
        "MPT Kids","WDVM-SD","Metro","XITOS","AltaVsn"
    ]
    tricky_channels = [normalize_channel(ch) for ch in tricky_channels]

    # Match channels
    found_channels = {}
    not_found_channels = {}
    for master in master_channels:
        norm_master = normalize_channel(master)
        matched = None
        for epg_norm, original in normalized_epg.items():
            if norm_master in epg_norm or epg_norm in norm_master:
                matched = original
                break
            if norm_master in tricky_channels and norm_master in epg_norm:
                matched = original
                break
        if matched:
            found_channels[master] = matched
        else:
            not_found_channels[master] = None

    # Create merged XML
    root = ET.Element("tv")
    for ch_name, elem in found_channels.items():
        ET.SubElement(root, "channel", id=ch_name)
    tree = ET.ElementTree(root)
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    merged_file = "merged_epg.xml.gz"
    with gzip.open(merged_file, "wb") as f:
        f.write(xml_bytes)

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
<table border="1" style="table-layout:fixed; width:600px; word-wrap:break-word;">
<tr><th>Master List</th><th>Matched EPG Channel</th></tr>
{''.join([f"<tr><td>{m}</td><td>{v}</td></tr>" for m,v in found_channels.items()])}
</table>

<h2>Channels Not Found</h2>
<table border="1" style="table-layout:fixed; width:600px; word-wrap:break-word;">
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

