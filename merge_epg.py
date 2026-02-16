import os
import pytz
import requests
import gzip
import io
from lxml import etree
from datetime import datetime


# ==========================
# NORMALIZE CHANNEL NAME
# ==========================
def normalize_channel_name(name):
    if not name:
        return None

    # Basic normalization (safe + predictable)
    name = name.strip().lower()
    return name


# ==========================
# FETCH + PARSE EPG SOURCE
# ==========================
def fetch_and_parse_epg(url):
    try:
        print(f"Trying to fetch {url}")
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        content = response.content

        # Handle gzipped XML files
        if url.endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                content = gz.read()

        parser = etree.XMLParser(recover=True, encoding="utf-8")
        root = etree.fromstring(content, parser=parser)

        channels = []
        for channel in root.findall("channel"):
            channel_id = channel.get("id")
            if channel_id:
                normalized = normalize_channel_name(channel_id)
                if normalized:
                    channels.append(normalized)

        print(f"Successfully parsed {len(channels)} channels from {url}")
        return channels

    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
        return []


# ==========================
# LOAD MASTER CHANNEL LIST
# ==========================
def load_master_channels(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        channels = f.readlines()

    channels = [
        normalize_channel_name(line)
        for line in channels
        if line.strip() and not line.startswith("#")
    ]

    return channels


# ==========================
# UPDATE INDEX.HTML
# ==========================
def update_index_page(channels_count, programs_count, file_size,
                      log_data, found_channels,
                      not_found_channels, master_channels):

    eastern = pytz.timezone("US/Eastern")
    last_updated = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S")

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
    <tr><th>Channel Name</th></tr>
    {''.join([f"<tr><td>{channel}</td></tr>" for channel in sorted(found_channels)])}
    </table>

    <h3>Channels Not Found:</h3>
    <table border="1">
    <tr><th>Channel Name</th></tr>
    {''.join([f"<tr><td>{channel}</td></tr>" for channel in sorted(not_found_channels)])}
    </table>
</div>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as file:
        file.write(html_content)

    print("index.html has been updated.")


# ==========================
# MAIN PROCESS
# ==========================
def main():

    # Load master channel list
    master_channels = load_master_channels("master_channels.txt")
    print(f"Loaded {len(master_channels)} channels from master list.")

    # Load EPG source URLs
    with open("epg_sources.txt", "r", encoding="utf-8") as f:
        epg_sources = [line.strip() for line in f if line.strip()]

    found_channels = set()
    not_found_channels = set()
    log_data = []
    total_programs = 0  # Placeholder for future real merge

    for url in epg_sources:
        epg_channels = fetch_and_parse_epg(url)

        for channel in epg_channels:
            if channel in master_channels:
                found_channels.add(channel)
            else:
                not_found_channels.add(channel)

        log_data.append(
            f"Processed {url} - Found {len(epg_channels)} channels"
        )

    # Calculate merged file size if exists
    final_file = "merged_epg.xml.gz"
    final_size = (
        os.path.getsize(final_file) / (1024 * 1024)
        if os.path.exists(final_file)
        else 0
    )

    update_index_page(
        channels_count=len(found_channels),
        programs_count=total_programs,
        file_size=final_size,
        log_data="\n".join(log_data),
        found_channels=found_channels,
        not_found_channels=not_found_channels,
        master_channels=master_channels
    )


if __name__ == "__main__":
    main()

