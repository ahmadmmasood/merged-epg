import os
import gzip
import requests
from datetime import datetime
import pytz

# Read channels from the master list file
def load_master_channels(file_path):
    try:
        with open(file_path, 'r') as file:
            channels = [line.strip().lower() for line in file.readlines() if line.strip()]
        return channels
    except Exception as e:
        print(f"Error reading master channels list: {e}")
        return []

# Parse the XML or TXT EPG files
def parse_epg_file(file_url):
    try:
        # Get the file from the URL
        response = requests.get(file_url)
        response.raise_for_status()

        # Check if the file is gzipped
        if file_url.endswith('.gz'):
            content = gzip.decompress(response.content).decode('utf-8')
        else:
            content = response.text

        return content
    except Exception as e:
        print(f"Error fetching or parsing file {file_url}: {e}")
        return ""

# Extract channels and programs from the EPG data
def extract_channels_and_programs(epg_data, master_channels):
    channels_found = set()
    programs_found = set()

    # Process each line in the EPG data
    for line in epg_data.splitlines():
        line = line.strip().lower()

        # Check for matching channels based on master list
        for channel in master_channels:
            if channel in line:
                channels_found.add(channel)

        # Assuming the line contains program data (simple example)
        if "<title>" in line:
            programs_found.add(line)

    return channels_found, programs_found

# Update the index.html with dynamic content
def update_index_page(channels_count, programs_count, file_size, log_data, master_channels, channels_found):
    try:
        # Set timezone to Eastern Time
        eastern = pytz.timezone('US/Eastern')
        last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

        # Calculate channels found and not found
        channels_not_found = set(master_channels) - channels_found
        channels_found_count = len(channels_found)
        channels_not_found_count = len(channels_not_found)
        total_channels_count = len(master_channels)

        # Prepare the HTML content with dynamic data
        html_content = f"""
        <html>
        <head><title>EPG Merge Status</title></head>
        <body>
        <h1>EPG Merge Status</h1>
        <p><strong>Last updated:</strong> {last_updated}</p>
        <p><strong>Channels kept:</strong> {channels_count}</p>
        <p><strong>Programs kept:</strong> {programs_count}</p>
        <p><strong>Final merged file size:</strong> {file_size:.2f} MB</p>

        <h2>Analysis:</h2>
        <p><strong>Total Channels in Master List:</strong> {total_channels_count}</p>
        <p><strong>Channels Found in EPG Files:</strong> {channels_found_count}</p>
        <p><strong>Channels Not Found:</strong> {channels_not_found_count}</p>
        <button onclick="document.getElementById('analysis').style.display='block'">Show Analysis</button>
        <button onclick="document.getElementById('analysis').style.display='none'">Hide Analysis</button>
        <div id="analysis" style="display:none;">
            <h3>Channels Not Found:</h3>
            <ul>
            {"".join([f"<li>{ch}</li>" for ch in channels_not_found])}
            </ul>
        </div>

        <h2>Logs:</h2>
        <button onclick="document.getElementById('logs').style.display='block'">Show Logs</button>
        <button onclick="document.getElementById('logs').style.display='none'">Hide Logs</button>
        <div id="logs" style="display:none;">
            <pre>{log_data}</pre>
        </div>
        </body>
        </html>
        """
        
        # Ensure the correct path for the file
        index_file_path = "index.html"

        # Write the content to the index.html file
        with open(index_file_path, "w") as file:
            file.write(html_content)

        print(f"{index_file_path} has been updated.")
    except Exception as e:
        print(f"Error updating index page: {e}")

# Main function to drive the process
def merge_epg():
    # Load master channels from the text file
    master_channels = load_master_channels('master_channels.txt')

    if not master_channels:
        print("No master channels found. Exiting.")
        return

    # List of EPG file URLs (both XML and TXT)
    epg_urls = [
        "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
        "https://www.open-epg.com/files/unitedstates10.xml.gz",
        "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
        "https://iptv-epg.org/files/epg-eg.xml.gz",
        "https://iptv-epg.org/files/epg-in.xml.gz",
        "https://www.open-epg.com/files/egypt1.xml.gz",
        "https://www.open-epg.com/files/egypt2.xml.gz",
        "https://www.open-epg.com/files/india3.xml.gz",
        "https://www.open-epg.com/files/unitedstates10.xml.gz"
    ]

    channels_found = set()
    programs_found = set()
    log_data = ""

    # Process each EPG file
    for epg_url in epg_urls:
        print(f"Processing: {epg_url}")
        epg_data = parse_epg_file(epg_url)
        if epg_data:
            found_channels, found_programs = extract_channels_and_programs(epg_data, master_channels)
            channels_found.update(found_channels)
            programs_found.update(found_programs)
            log_data += f"Processed {epg_url} - Found {len(found_channels)} channels and {len(found_programs)} programs.\n"

    # Calculate the merged file size (simplified for now, you can calculate this more accurately if needed)
    merged_file_size = len(channels_found) * 0.1  # Just a placeholder for the size in MB

    # Update the index page with the results
    update_index_page(len(channels_found), len(programs_found), merged_file_size, log_data, master_channels, channels_found)

# Run the merge process
merge_epg()

