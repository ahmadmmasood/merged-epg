import os
import pytz
import requests
from datetime import datetime
from epg_handler import fetch_and_parse_epg, normalize_channel_name

# Function to load the master channels
def load_master_channels(file_path):
    with open(file_path, "r") as f:
        channels = f.readlines()
    channels = [line.strip() for line in channels if line.strip() and not line.startswith("#")]
    return channels

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
    
    # Read the list of EPG sources from a file
    epg_sources = []
    with open("epg_sources.txt", "r") as f:
        epg_sources = [line.strip() for line in f.readlines() if line.strip()]
    
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
                
                if normalized_channel and normalized_channel in master_channels:
                    found_channels.append(normalized_channel)
                elif normalized_channel:
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

