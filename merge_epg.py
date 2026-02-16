import xml.etree.ElementTree as ET
import gzip
import os

MASTER_FILE = "master_channels.txt"
EPG_FILES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.txt",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.txt",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]
MERGED_FILE = "merged.xml.gz"
INDEX_FILE = "index.html"

def fetch_content(file_path):
    if file_path.startswith("http"):
        import requests
        r = requests.get(file_path)
        r.raise_for_status()
        content = r.content
    else:
        with open(file_path, "rb") as f:
            content = f.read()
    return content

def normalize_channel(name):
    name = name.lower()
    for x in ['.us2', '.us_locals1', '.', '-', 'hd', 'hdtv']:
        name = name.replace(x, ' ')
    for region in ['pacific', 'west']:
        name = name.replace(region, '')
    name = ' '.join(name.split())  # remove extra spaces
    return name

# Load master channels
with open(MASTER_FILE) as f:
    master_channels = [line.strip() for line in f if line.strip()]

# Parse EPG files
epg_channels = {}
for epg_file in EPG_FILES:
    try:
        content = fetch_content(epg_file)
        # Handle gzipped XML
        if epg_file.endswith(".gz"):
            content = gzip.decompress(content)
        try:
            root = ET.fromstring(content)
            # XML mode
            for channel in root.findall("channel"):
                chid = channel.attrib.get("id", "")
                epg_channels[chid] = normalize_channel(chid)
        except ET.ParseError:
            # TXT mode
            for line in content.decode(errors='ignore').splitlines():
                line = line.strip()
                if line:
                    epg_channels[line] = normalize_channel(line)
    except Exception as e:
        print(f"Error fetching/parsing {epg_file}: {e}")

# Matching master channels to EPG
found_channels = {}
not_found_channels = {}
for master in master_channels:
    norm_master = normalize_channel(master)
    matched = None
    for epg_raw, epg_norm in epg_channels.items():
        if 'pacific' in epg_raw.lower() or 'west' in epg_raw.lower():
            continue
        if norm_master in epg_norm or epg_norm in norm_master:
            matched = epg_raw
            break
    if matched:
        found_channels[master] = matched
    else:
        not_found_channels[master] = None

# Build merged XML
merged_root = ET.Element("tv")
for master, epg_id in found_channels.items():
    ch = ET.SubElement(merged_root, "channel", id=epg_id)
    ET.SubElement(ch, "display-name").text = master

xml_str = ET.tostring(merged_root, encoding='utf-8', xml_declaration=True)
with gzip.open(MERGED_FILE, "wb") as f:
    f.write(xml_str)

# File size
merged_size = os.path.getsize(MERGED_FILE) / (1024 * 1024)

# Update index.html
with open(INDEX_FILE, "w") as f:
    f.write(f"""
<html>
<head><title>EPG Merge Report</title></head>
<body>
<h2>EPG Merge Report</h2>
<p>Total channels in master list: {len(master_channels)}</p>
<p>Channels found: {len(found_channels)}</p>
<p>Channels not found: {len(not_found_channels)}</p>
<p>Final merged file size: {merged_size:.2f} MB</p>
</body>
</html>
""")

print(f"Total channels in master list: {len(master_channels)}")
print(f"Channels found: {len(found_channels)}")
print(f"Channels not found: {len(not_found_channels)}")
print(f"Final merged file size: {merged_size:.2f} MB")

