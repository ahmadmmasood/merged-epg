import requests
import gzip
import xml.etree.ElementTree as ET
import pytz
from datetime import datetime
import os

# Define the EPG sources and master channel list path
epg_sources = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz"
]

# Load channels from the master list file
def load_channels_from_master_list(file_path):
    channels = []
    with open(file_path, 'r') as f:
        for line in f:
            # Ignore lines that are either comments or section headers (lines starting with "#")
            if line.strip() and not line.startswith("#"):
                channels.append(line.strip().lower())  # Add lowercase version for case-insensitivity
    return channels

# Fetch and parse an XML or TXT EPG source
def fetch_and_parse_epg(url):
    try:
        response = requests.get(url)
        response.raise_for_status()

        if url.endswith('.gz'):
            with gzip.GzipFile(fileobj=response.content) as f:
                file_content = f.read().decode('utf-8')
        else:
            file_content = response.text

        return file_content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching/parsing {url}: {e}")
        return None

# Parse XML and search for the channels from the master list
def parse_xml(epg_content, channels):
    found_channels = []
    tree = ET.ElementTree(ET.fromstring(epg_content))
    root = tree.getroot()

    for channel in root.iter('channel'):
        channel_name = channel.find('display-name').text.strip().lower()
        if channel_name in channels:
            found_channels.append(channel_name)
    
    return found_channels

# Generate the HTML index page with dynamic stats
def update_index_page(channels_count, programs_count, file_size, found_channels, total_channels):
    # Calculate missing channels
    missing_channels = [ch for ch in total_channels if ch not in found_channels]
    # Set timezone to Eastern Time
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

    # Prepare HTML content
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
        <pre>{str(epg_sources)}</pre>
    </div>

    <h2>Channel Analysis:</h2>
    <button onclick="document.getElementById('analysis').style.display='block'">Show Analysis</button>
    <button onclick="document.getElementById('analysis').style.display='none'">Hide Analysis</button>
    <div id="analysis" style="display:none;">
        <pre>
        Total Channels in Master List: {len(total_channels)}
        Channels Found: {len(found_channels)}
        Channels Not Found: {len(missing_channels)}
        </pre>
    </div>
    </body>
    </html>
    """
    # Write the content to the index.html file
    with open("index.html", "w") as file:
        file.write(html_content)
    print("index.html has been updated.")

# Main process
def main():
    total_channels = load_channels_from_master_list('master_channels.txt')  # Load the channels from the master list
    found_channels = []
    total_programs = 0
    total_file_size = 0

    for url in epg_sources:
        print(f"Processing {url}...")
        epg_content = fetch_and_parse_epg(url)
        if epg_content:
            if url.endswith('.xml.gz'):
                found = parse_xml(epg_content, total_channels)
                found_channels.extend(found)
                total_file_size += len(epg_content) / 1024 / 1024  # Convert bytes to MB

    # Remove duplicates from found_channels
    found_channels = list(set(found_channels))

    # Update index page with stats
    update_index_page(len(found_channels), total_programs, total_file_size, found_channels, total_channels)

if __name__ == "__main__":
    main()

