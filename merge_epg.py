import os
import gzip
import xml.etree.ElementTree as ET
from urllib.request import urlopen

MASTER_LIST_FILE = "master_channels.txt"
MERGED_FILE = "merged.xml.gz"
INDEX_FILE = "index.html"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.txt",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.txt",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
]

def fetch_content(url):
    try:
        resp = urlopen(url)
        data = resp.read()
        if url.endswith(".gz"):
            return gzip.decompress(data)
        return data
    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
        return b""

def parse_epg(content, url):
    channels = []
    try:
        if url.endswith(".xml") or url.endswith(".xml.gz"):
            root = ET.fromstring(content)
            for ch in root.findall("channel"):
                ch_id = ch.attrib.get("id") or ""
                display_name = ch.findtext("display-name") or ""
                channels.append(display_name.strip())
        else:  # assume text list of channels
            for line in content.decode("utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line:
                    channels.append(line)
    except ET.ParseError:
        # fallback for malformed xml, treat as text
        for line in content.decode("utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line:
                channels.append(line)
    return channels

def normalize(name):
    name = name.lower()
    name = name.replace("hd", "").replace("hdtv", "")
    name = name.replace("-", " ").replace(".", " ").replace("_", " ")
    for skip in ["pacific", "west"]:
        if skip in name:
            return None
    return name.strip()

def match_channels(parsed_channels, master_channels):
    found = {}
    not_found = {}
    normalized_master = {normalize(ch): ch for ch in master_channels}
    for ch in parsed_channels:
        n = normalize(ch)
        if not n:
            continue
        # Check if any master channel is contained in the parsed channel
        matched_master = None
        for nm, mc in normalized_master.items():
            if nm and nm in n:
                matched_master = mc
                break
        if matched_master:
            found[matched_master] = ch
        else:
            not_found[ch] = ch
    # Channels from master list not matched
    master_not_found = {mc: mc for mc in master_channels if mc not in found}
    return found, master_not_found

def write_merged_xml(channels):
    root = ET.Element("tv")
    for master_ch, epg_ch in channels.items():
        ch_elem = ET.SubElement(root, "channel", id=master_ch)
        name_elem = ET.SubElement(ch_elem, "display-name")
        name_elem.text = epg_ch
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with gzip.open(MERGED_FILE, "wb") as f:
        f.write(xml_bytes)
    size_mb = os.path.getsize(MERGED_FILE) / (1024 * 1024)
    return size_mb

def load_master_channels():
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def update_index_html(total, found_count, not_found_count, merged_size, found_channels, not_found_channels):
    html = f"""
<html>
<head>
<title>iEPG Merge Report</title>
<style>
table {{border-collapse: collapse; width: 100%;}}
th, td {{border: 1px solid #ccc; padding: 5px; text-align: left;}}
.details {{display:none;}}
.toggle {{cursor:pointer; color:blue; text-decoration:underline;}}
</style>
<script>
function toggle(id) {{
    var e = document.getElementById(id);
    e.style.display = e.style.display === 'none' ? 'table-row-group' : 'none';
}}
</script>
</head>
<body>
<h2>iEPG Merge Report</h2>
<p>Total channels in master list: {total}</p>
<p>Channels found: {found_count} (<span class="toggle" onclick="toggle('found')">show/hide</span>)</p>
<p>Channels not found: {not_found_count} (<span class="toggle" onclick="toggle('notfound')">show/hide</span>)</p>
<p>Final merged file size: {merged_size:.2f} MB</p>

<table id="found" class="details">
<tr><th>Master Channel</th><th>EPG Channel</th></tr>
"""
    for mc, epg in found_channels.items():
        html += f"<tr><td>{mc}</td><td>{epg}</td></tr>\n"
    html += "</table>\n"

    html += '<table id="notfound" class="details">\n<tr><th>Master Channel</th></tr>\n'
    for mc in not_found_channels.keys():
        html += f"<tr><td>{mc}</td></tr>\n"
    html += "</table>\n</body>\n</html>"

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    master_channels = load_master_channels()
    total_master = len(master_channels)
    parsed_channels_all = []

    for url in EPG_SOURCES:
        print(f"Fetching {url}")
        content = fetch_content(url)
        parsed = parse_epg(content, url)
        print(f"Processed {url} - Parsed {len(parsed)} channels")
        parsed_channels_all.extend(parsed)

    found_channels, not_found_channels = match_channels(parsed_channels_all, master_channels)
    merged_size = write_merged_xml(found_channels)

    print(f"Total channels in master list: {total_master}")
    print(f"Channels found: {len(found_channels)}")
    print(f"Channels not found: {len(not_found_channels)}")
    print(f"Final merged file size: {merged_size:.2f} MB")

    update_index_html(total_master, len(found_channels), len(not_found_channels), merged_size, found_channels, not_found_channels)
    print(f"{INDEX_FILE} has been updated.")

if __name__ == "__main__":
    main()

