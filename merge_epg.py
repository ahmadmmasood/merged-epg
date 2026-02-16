import os
import re
import gzip
import pytz
import requests
from io import BytesIO
from datetime import datetime
from xml.etree import ElementTree as ET

MERGED_FILE = "merged_epg.xml.gz"

# =========================
# Normalization Function
# =========================
def normalize_channel_name(name):
    if not name:
        return None

    name = name.strip()
    name = re.sub(r"^\d+\.\d+\s*", "", name)  # Remove channel numbers
    name = re.sub(r"\.(us\d+|locals\d+|us_locals\d+)$", "", name, flags=re.IGNORECASE)
    name = name.replace(".", " ")
    name = re.sub(r"\bhd\b|\bhdtv\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\beast\b", "", name, flags=re.IGNORECASE)
    if re.search(r"\b(west|pacific)\b", name, flags=re.IGNORECASE):
        return None
    name = re.sub(r"\s+", " ", name)
    name = name.rstrip("-").strip()
    return name.lower()

# =========================
# Fetch and Parse EPG
# =========================
def fetch_and_parse_epg(url):
    print(f"Fetching {url}")
    parsed_channels = []
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
        return []

    try:
        if url.endswith(".xml.gz"):
            with gzip.GzipFile(fileobj=BytesIO(content)) as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for channel in root.findall(".//channel"):
                    ch_name = channel.get("name") or channel.findtext("display-name")
                    if ch_name:
                        parsed_channels.append(ch_name)
        else:
            # TXT file
            lines = content.decode("utf-8", errors="ignore").splitlines()
            for line in lines:
                if line.strip():
                    parsed_channels.append(line.strip())
    except Exception as e:
        print(f"Error parsing XML from {url}: {e}")

    print(f"Processed {url} - Parsed {len(parsed_channels)} channels")
    return parsed_channels

# =========================
# Load Master Channels
# =========================
def load_master_channels(file_path):
    with open(file_path, "r") as f:
        channels = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return channels

# =========================
# Write Merged XML
# =========================
def write_merged_xml(channels_set, master_normalized):
    root = ET.Element("tv")
    for norm_name in sorted(channels_set):
        ch_elem = ET.SubElement(root, "channel")
        ch_elem.set("name", master_normalized[norm_name])
    tree = ET.ElementTree(root)
    with gzip.open(MERGED_FILE, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

# =========================
# Update index.html
# =========================
def update_index_page(found_channels, not_found_channels, log_data, master_channels):
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')
    file_size = os.path.getsize(MERGED_FILE) / (1024*1024) if os.path.exists(MERGED_FILE) else 0

    html_content = f"""
<html>
<head>
    <title>EPG Merge Status</title>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .found {{ background-color: #d4edda; }}
        .notfound {{ background-color: #f8d7da; }}
        .log {{ white-space: pre-wrap; background-color: #eee; padding: 10px; }}
    </style>
</head>
<body>
<h1>EPG Merge Status</h1>
<p><strong>Last updated:</strong> {last_updated}</p>
<p><strong>Channels kept:</strong> {len(found_channels)}</p>
<p><strong>Final merged file size:</strong> {file_size:.2f} MB</p>
<p><strong>Total channels in master list:</strong> {len(master_channels)}</p>

<h2>Logs</h2>
<div class="log">{log_data}</div>

<h2>Channel Analysis</h2>

<h3>Channels Found</h3>
<table>
<tr><th>Original Channel</th><th>Normalized</th><th>Matched?</th></tr>
{''.join([f'<tr class="found"><td>{orig}</td><td>{norm}</td><td>Yes</td></tr>' for orig, norm in found_channels])}
</table>

<h3>Channels Not Found</h3>
<table>
<tr><th>Original Channel</th><th>Normalized</th><th>Matched?</th></tr>
{''.join([f'<tr class="notfound"><td>{orig}</td><td>{norm}</td><td>No</td></tr>' for orig, norm in not_found_channels])}
</table>

</body>
</html>
"""
    with open("index.html", "w") as f:
        f.write(html_content)
    print("index.html has been updated.")

# =========================
# Main Merge Process
# =========================
def main():
    master_channels = load_master_channels("master_channels.txt")
    master_normalized = {normalize_channel_name(ch): ch for ch in master_channels}

    with open("epg_sources.txt", "r") as f:
        epg_sources = [line.strip() for line in f if line.strip()]

    found_channels = []
    not_found_channels = []
    log_data_list = []

    merged_channels_set = set()

    for url in epg_sources:
        parsed_channels = fetch_and_parse_epg(url)
        for ch in parsed_channels:
            norm_ch = normalize_channel_name(ch)
            if not norm_ch:
                continue
            matched = norm_ch in master_normalized
            if matched:
                merged_channels_set.add(norm_ch)
                found_channels.append((ch, norm_ch))
            else:
                not_found_channels.append((ch, norm_ch))
            log_data_list.append(f"Parsed: {ch} -> Normalized: {norm_ch} -> Matched: {'Yes' if matched else 'No'}")

    # Write merged XML.gz with only matched channels
    write_merged_xml(merged_channels_set, master_normalized)

    # Join log data for HTML
    log_data = "\n".join(log_data_list)

    # Update index.html
    update_index_page(found_channels, not_found_channels, log_data, master_channels)

if __name__ == "__main__":
    main()

