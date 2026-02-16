import os
import re
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
import pytz

# Load master channel list (adjust this to your file location)
def load_master_channels(file_path):
    master_channels = []
    try:
        with open(file_path, "r") as file:
            for line in file:
                # Strip whitespace and ignore lines starting with #
                if line.strip() and not line.startswith('#'):
                    master_channels.append(normalize_channel_name(line.strip()))
    except Exception as e:
        print(f"Error loading master channels: {e}")
    return master_channels


# Normalize channel names (strip unwanted suffixes and regions)
def normalize_channel_name(channel_name):
    # Remove unwanted suffixes and variations
    suffixes_to_remove = [
        'hd', 'hdtv', 'us2', 'us_locals1', 'pacific', 'west', 'east', 'tv', 'channel', 'network'
    ]
    channel_name = channel_name.lower()  # Case-insensitive matching
    for suffix in suffixes_to_remove:
        # Remove suffixes except numbers (e.g. don't remove "HBO 2")
        channel_name = re.sub(f'(\.{suffix})$', '', channel_name)
    # Remove any remaining '.' in the name
    channel_name = re.sub(r'\.', ' ', channel_name)
    # Remove "hd" or "hdtv" from the end, but not in the middle
    channel_name = re.sub(r'(hd|hdtv)\s*$', '', channel_name)
    return channel_name.strip()


# Fetch and parse EPG data
def fetch_and_parse_epg(url):
    print(f"Trying to fetch {url}")
    if url.endswith('.txt'):
        return fetch_txt_data(url)
    elif url.endswith('.xml.gz'):
        return fetch_xml_data(url)
    else:
        print(f"Unsupported file format: {url}")
        return []


def fetch_txt_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
        channels = parse_txt_data(content)
        return channels
    except Exception as e:
        print(f"Error fetching/parsing TXT file: {e}")
        return []


def fetch_xml_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.content
        return parse_xml_data(content)
    except Exception as e:
        print(f"Error fetching/parsing XML file: {e}")
        return []


def parse_txt_data(content):
    channels = []
    lines = content.splitlines()
    for line in lines:
        if not line.startswith('#') and len(line.strip()) > 0:
            normalized_name = normalize_channel_name(line)
            channels.append(normalized_name)
    return channels


def parse_xml_data(content):
    channels = []
    try:
        root = ET.fromstring(content)
        for channel in root.findall('.//channel'):
            name = channel.find('display-name').text
            if name:
                normalized_name = normalize_channel_name(name)
                channels.append(normalized_name)
    except ET.ParseError as e:
        print(f"Error parsing XML content: {e}")
    return channels


# Update the index page with the latest data
def update_index_page(channels_count, programs_count, file_size, log_data, found_channels, not_found_channels):
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

    # Prepare the HTML content
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
        <p><strong>Total Channels in Master List:</strong> 229</p>
        <p><strong>Channels Found:</strong> {channels_count}</p>
        <p><strong>Channels Not Found:</strong> {len(not_found_channels)}</p>

        <h3>Channels Found:</h3>
        <table border="1">
        <tr><th>Channel Name</th></tr>
        {''.join([f"<tr><td>{channel}</td></tr>" for channel in found_channels])}
        </table>

        <h3>Channels Not Found:</h3>
        <table border="1">
        <tr><th>Channel Name</th></tr>
        {''.join([f"<tr><td>{channel}</td></tr>" for channel in not_found_channels])}
        </table>
    </div>
    </body>
    </html>
    """

    with open("index.html", "w") as file:
        file.write(html_content)
    print("index.html has been updated.")


# Main function
def main():
    # Load your master list of channels from a file (e.g., master_channels.txt)
    master_channels = load_master_channels('master_channels.txt')

    epg_sources = [
        "https://epgshare01.online/epgshare01/epg_ripper_US2.txt",
        "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.txt",
        "https://iptv-epg.org/files/epg-eg.xml.gz",
        "https://iptv-epg.org/files/epg-in.xml.gz",
        "https://iptv-epg.org/files/epg-lb.xml.gz",
        "https://www.open-epg.com/files/egypt1.xml.gz",
        "https://www.open-epg.com/files/egypt2.xml.gz",
        "https://www.open-epg.com/files/india3.xml.gz"
    ]
    
    total_channels = []
    found_channels = []
    not_found_channels = []
    log_data = []

    # Iterate through each URL and fetch the data
    for url in epg_sources:
        channels = fetch_and_parse_epg(url)
        log_data.append(f"Processing {url} - Found {len(channels)} channels")
        total_channels.extend(channels)

    # Identify channels found and not found
    for channel in total_channels:
        if channel in master_channels:  # Compare with the master list
            found_channels.append(channel)
        else:
            not_found_channels.append(channel)

    # Prepare index page content
    update_index_page(
        channels_count=len(found_channels),
        programs_count=0,  # Add your logic to count programs
        file_size=37.00,  # Calculate actual size if necessary
        log_data="\n".join(log_data),
        found_channels=found_channels,
        not_found_channels=not_found_channels
    )


if __name__ == "__main__":
    main()

