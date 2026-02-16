import xml.etree.ElementTree as ET
import requests
import os
from datetime import datetime
import pytz
import re

# Function to normalize channel names by removing unwanted suffixes, regions, and keeping numbers in names
def normalize_channel_name(channel_name):
    # Convert to lowercase for consistent comparison
    normalized_name = channel_name.lower()

    # Remove suffixes at the end like .us2, .us_locals1, .hd, .hdtv, .us, .dt, .cd, and any numbers ending
    normalized_name = re.sub(r'\.(us2|us_locals1|hd|hdtv|us|dt|cd|1|2|3|4)$', '', normalized_name)
    
    # Replace any remaining dots with spaces
    normalized_name = re.sub(r'\.', ' ', normalized_name).strip()

    # Skip channels that mention "pacific" or "west" in their name
    if "pacific" in normalized_name or "west" in normalized_name:
        return None  # Returning None to indicate we should skip this channel

    # Return the cleaned name
    return normalized_name

# Function to fetch and parse EPG data
def fetch_and_parse_epg(url):
    try:
        response = requests.get(url)
        response.raise_for_status()

        if url.endswith(".xml.gz"):
            epg_content = response.content
            return epg_content
        elif url.endswith(".txt"):
            epg_content = response.text
            return epg_content
        else:
            raise ValueError("Unsupported file format")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching/parsing {url}: {e}")
        return None

# Function to parse the XML data
def parse_xml(epg_content, total_channels):
    try:
        tree = ET.ElementTree(ET.fromstring(epg_content))
        root = tree.getroot()
        
        # Extract channels
        channels = []
        for channel in root.findall('.//channel'):
            display_name = channel.find('display-name').text
            if display_name:
                normalized_channel_name = normalize_channel_name(display_name)
                if normalized_channel_name and normalized_channel_name in total_channels:
                    channels.append(normalized_channel_name)
        return channels
    except ET.ParseError as e:
        print(f"Error parsing XML content: {e}")
        return []

# Function to parse TXT data
def parse_txt(epg_content, total_channels):
    lines = epg_content.splitlines()
    found_channels = []
    for line in lines:
        normalized_channel_name = normalize_channel_name(line)
        if normalized_channel_name and normalized_channel_name in total_channels:
            found_channels.append(normalized_channel_name)
    return found_channels

# Function to update the index.html page
def update_index_page(channels_count, programs_count, file_size, found_channels, not_found_channels, log_data):
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')
    
    found_channels_html = "<ul>"
    for channel in found_channels:
        found_channels_html += f"<li>{channel}</li>"
    found_channels_html += "</ul>"

    not_found_channels_html = "<ul>"
    for channel in not_found_channels:
        not_found_channels_html += f"<li>{channel}</li>"
    not_found_channels_html += "</ul>"

    # Prepare HTML content for the index page
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
        {log_data}
    </div>

    <h2>Channel Analysis:</h2>
    <button onclick="document.getElementById('analysis').style.display='block'">Show Analysis</button>
    <button onclick="document.getElementById('analysis').style.display='none'">Hide Analysis</button>
    <div id="analysis" style="display:none;">
        <p>Total Channels in Master List: {len(total_channels)}</p>
        <p>Channels Found: {len(found_channels)}</p>
        <p>Channels Not Found: {len(not_found_channels)}</p>
        <h3>Channels Found:</h3>
        {found_channels_html}
        <h3>Channels Not Found:</h3>
        {not_found_channels_html}
    </div>
    </body>
    </html>
    """
    
    with open("index.html", "w") as file:
        file.write(html_content)

# Main function to handle the EPG merging process
def main():
    total_channels = set()  # This will contain all the channels from the master list
    found_channels = []
    not_found_channels = []
    log_data = []

    # Load the master channel list (replace this with your actual master list reading logic)
    with open("master_channels.txt") as file:
        for line in file:
            # Ignore lines starting with "#" or empty lines
            if not line.startswith("#") and line.strip():
                total_channels.add(normalize_channel_name(line.strip()))

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

    total_programs = 0  # This will hold the total number of programs found
    total_channels_found = 0

    for url in epg_sources:
        log_data.append(f"Processing {url}...")

        epg_content = fetch_and_parse_epg(url)
        if epg_content:
            if url.endswith(".txt"):
                channels = parse_txt(epg_content, total_channels)
            elif url.endswith(".xml.gz"):
                channels = parse_xml(epg_content, total_channels)
            
            found_channels.extend(channels)
            total_channels_found += len(channels)
            log_data.append(f"{url} - Found {len(channels)} channels")
        else:
            log_data.append(f"{url} - Failed to fetch or parse")

    not_found_channels = list(total_channels - set(found_channels))

    update_index_page(len(found_channels), total_programs, 37.00, found_channels, not_found_channels, "\n".join(log_data))

if __name__ == "__main__":
    main()

