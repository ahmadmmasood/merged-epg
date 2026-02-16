import os
import gzip
import pytz
import requests
from datetime import datetime
import xml.etree.ElementTree as ET

# Function to load the master channels
def load_master_channels(file_path):
    with open(file_path, "r") as f:
        channels = f.readlines()
    channels = [line.strip() for line in channels if line.strip() and not line.startswith("#")]
    return channels

# Function to parse XML files
def parse_xml(epg_content):
    try:
        tree = ET.ElementTree(ET.fromstring(epg_content))
        root = tree.getroot()
        return [channel.find("display-name").text for channel in root.findall("channel")]
    except ET.ParseError:
        print(f"Error parsing XML content.")
        return []

# Function to fetch and parse EPG content from a URL
def fetch_and_parse_epg(url):
    print(f"Trying to fetch {url}")
    try:
        if url.endswith(".txt"):
            response = requests.get(url)
            response.raise_for_status()
            print(f"Successfully fetched TXT file from {url}")
            return response.text.splitlines()
        elif url.endswith(".xml.gz"):
            response = requests.get(url)
            response.raise_for_status()
            with gzip.open(response.content, 'rb') as f:
                return parse_xml(f.read().decode("utf-8"))
        else:
            print(f"Unsupported URL type: {url}")
            return []
    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
        return []

# Function to update the index.html page with status and analysis
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

# Main function to execute the merge process
def main():
    # Load the master channels
    master_channels = load_master_channels("master_channels.txt")
    print(f"Loaded {len(master_channels)} channels from master list.")
    
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

    found_channels = []
    not_found_channels = []
    log_data = []
    total_programs = 0

    # Process each EPG source
    for url in epg_sources:
        epg_content = fetch_and_parse_epg(url)
        if epg_content:
            for channel in epg_content:
                # Normalize the channel name here
                normalized_channel = normalize_channel_name(channel)
                
                if normalized_channel in master_channels:
                    found_channels.append(normalized_channel)
                else:
                    not_found_channels.append(normalized_channel)

        log_data.append(f"Processed {url} - Found {len(epg_content)} channels")

    # Calculate the merged file size (just an example; replace with actual logic)
    final_merged_file_size = os.path.getsize("merged_epg.xml.gz") / (1024 * 1024) if os.path.exists("merged_epg.xml.gz") else 0

    # Update the index page with the status
    update_index_page(
        channels_count=len(found_channels),
        programs_count=total_programs,
        file_size=final_merged_file_size,
        log_data="\n".join(log_data),
        found_channels=found_channels,
        not_found_channels=not_found_channels,
        master_channels=master_channels
    )

if __name__ == "__main__":
    main()

