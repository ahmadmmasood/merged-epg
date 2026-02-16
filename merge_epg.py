import os
import re
import gzip
import pytz
import requests
from datetime import datetime
from xml.etree import ElementTree as ET

# =========================
# Normalization Function
# =========================
def normalize_channel_name(name):
    if not name:
        return None

    name = name.strip()

    # Remove leading channel numbers like "4.1", "22.2"
    name = re.sub(r"^\d+\.\d+\s*", "", name)

    # Remove suffixes like .us2, .locals1, .us_locals1
    name = re.sub(r"\.(us\d+|locals\d+|us_locals\d+)$", "", name, flags=re.IGNORECASE)

    # Replace dots with spaces
    name = name.replace(".", " ")

    # Remove HD / HDTV (but keep "UK", "Kids", "+", etc.)
    name = re.sub(r"\bhd\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\bhdtv\b", "", name, flags=re.IGNORECASE)

    # Remove east
    name = re.sub(r"\beast\b", "", name, flags=re.IGNORECASE)

    # Ignore west or pacific completely
    if re.search(r"\b(west|pacific)\b", name, flags=re.IGNORECASE):
        return None

    # Normalize spacing
    name = re.sub(r"\s+", " ", name)

    # Remove trailing hyphens unless they are part of master list symbols
    name = name.rstrip("-").strip()

    # Lowercase for comparison
    name = name.lower()

    return name

# =========================
# Fetch and Parse EPG
# =========================
def fetch_and_parse_epg(url):
    print(f"Fetching {url}")
    content = None
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
        return []

    parsed_channels = []

    # Determine file type
    if url.endswith(".xml.gz"):
        try:
            with gzip.open(url.split("/")[-1], "wb") as f:
                f.write(content)
            with gzip.open(url.split("/")[-1], "rb") as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for channel in root.findall(".//channel"):
                    ch_name = channel.get("name") or channel.findtext("display-name")
                    if ch_name:
                        parsed_channels.append(ch_name)
        except Exception as e:
            print(f"Error parsing XML from {url}: {e}")
    else:
        # TXT file
        try:
            lines = content.decode("utf-8", errors="ignore").splitlines()
            for line in lines:
                line = line.strip()
                if line:
                    parsed_channels.append(line)
        except Exception as e:
            print(f"Error parsing TXT from {url}: {e}")

    print(f"Processed {url} - Parsed {len(parsed_channels)} channels")
    return parsed_channels

# =========================
# Load Master Channels
# =========================
def load_master_channels(file_path):
    with open(file_path, "r") as f:
        channels = f.readlines()
    channels = [line.strip() for line in channels if line.strip() and not line.startswith("#")]
    return channels

# =========================
# Update index.html
# =========================
def update_index_page(channels_count, programs_count, file_size, log_data, found_channels, not_found_channels, master_channels):
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

    html_content = f"""
    <html>
    <head><title>EPG Merge Status</title></head>
    <body>
    <h1>EPG Merge Status</h1>
    <p><strong>Last updated:</strong> {last_updated}</p>
    <p><strong>Channels kept:</strong> {channels_count}</p>
    <p><strong>Programs kept:</strong> {programs_count}</p>
    <p><strong>Final merged file size:</strong> {file_size:.2f} MB</p>

    <h2>Logs:</h2>
    <button onclick="document.getElementById('logs').style.display='block'">Show Logs</button>
    <button onclick="document.getElementById('logs').style.display='none'">Hide Logs</button>
    <div id="logs" style="display:none;">
        <pre>{log_data}</pre>
    </div>

    <h2>Channel Analysis:</h2>
    <button onclick="document.getElementById('analysis').style.display='block'">Show Analysis</button>
    <button onclick="document.getElementById('analysis').style.display='none'">Hide Analysis</button>
    <div id="analysis" style="display:none;">
        <p><strong>Total Channels in Master List:</strong> {len(master_channels)}</p>
        <p><strong>Channels Found:</strong> {channels_count}</p>
        <p><strong>Channels Not Found:</strong> {len(not_found_channels)}</p>

        <h3>Channels Found:</h3>
        <table border="1">
        <tr><th>Original Channel</th><th>Normalized Name</th></tr>
        {''.join([f"<tr><td>{orig}</td><td>{norm}</td></tr>" for orig, norm in found_channels])}
        </table>

        <h3>Channels Not Found:</h3>
        <table border="1">
        <tr><th>Original Channel</th><th>Normalized Name</th></tr>
        {''.join([f"<tr><td>{orig}</td><td>{norm}</td></tr>" for orig, norm in not_found_channels])}
        </table>
    </div>
    </body>
    </html>
    """

    with open("index.html", "w") as file:
        file.write(html_content)
    print("index.html has been updated.")

# =========================
# Main Merge Process
# =========================
def main():
    # Load master channels
    master_channels = load_master_channels("master_channels.txt")
    master_normalized = {normalize_channel_name(ch): ch for ch in master_channels}

    # Load EPG sources
    with open("epg_sources.txt", "r") as f:
        epg_sources = [line.strip() for line in f if line.strip()]

    found_channels = []
    not_found_channels = []
    log_data = []
    total_programs = 0

    merged_channels_set = set()

    # Process each EPG source
    for url in epg_sources:
        parsed_channels = fetch_and_parse_epg(url)
        parsed_count = len(parsed_channels)

        for ch in parsed_channels:
            norm_ch = normalize_channel_name(ch)
            if not norm_ch:
                continue
            if norm_ch in master_normalized:
                merged_channels_set.add(norm_ch)
                found_channels.append((ch, norm_ch))
            else:
                not_found_channels.append((ch, norm_ch))

        log_data.append(f"Processed {url} - Parsed {parsed_count} channels")

    # Calculate final merged file size
    merged_file_path = "merged_epg.xml.gz"
    final_size = os.path.getsize(merged_file_path) / (1024 * 1024) if os.path.exists(merged_file_path) else 0

    # Update HTML index
    update_index_page(
        channels_count=len(merged_channels_set),
        programs_count=total_programs,
        file_size=final_size,
        log_data="\n".join(log_data),
        found_channels=found_channels,
        not_found_channels=not_found_channels,
        master_channels=master_channels
    )

if __name__ == "__main__":
    main()

