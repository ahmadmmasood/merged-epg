import os
import gzip
import pytz
from datetime import datetime

def load_master_channels(file_path):
    """ Load the master channel list from a text file """
    with open(file_path, 'r') as file:
        channels = [line.strip().lower() for line in file.readlines()]  # Make case-insensitive
    print(f"Loaded {len(channels)} channels from the master list.")
    return channels

def update_index_page(channels_count, programs_count, file_size, log_data):
    """ Update the index.html dynamically with the merge status data """
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
    </body>
    </html>
    """
    # Write the dynamic content to index.html
    with open("index.html", "w") as file:
        file.write(html_content)
    print("index.html has been updated.")

def parse_and_filter_channels(master_channels, epg_file):
    """ Parse the provided XML EPG file and filter based on the master list """
    filtered_channels = []
    log_data = ""
    
    try:
        if epg_file.endswith('.gz'):
            with gzip.open(epg_file, 'rt') as file:
                lines = file.readlines()
        else:
            with open(epg_file, 'r') as file:
                lines = file.readlines()

        log_data += f"Processing {epg_file}...\n"
        
        for line in lines:
            # Assume channel names are mentioned in lines (adjust this based on actual structure)
            channel_name = line.strip().lower()  # Normalize to lowercase for case-insensitive matching
            if channel_name in master_channels:
                filtered_channels.append(channel_name)
        
        log_data += f"Found {len(filtered_channels)} channels matching the master list in {epg_file}.\n"
        
    except Exception as e:
        log_data = f"Error processing file {epg_file}: {str(e)}"

    return filtered_channels, log_data

def write_merged_file(filtered_channels):
    """ Write the filtered channels into a merged XML file """
    merged_file = 'merged.xml.gz'
    with gzip.open(merged_file, 'wt') as f:
        f.write("<channels>\n")
        for channel in filtered_channels:
            f.write(f"  <channel><name>{channel}</name></channel>\n")
        f.write("</channels>")
    return merged_file

def process_epg_data():
    """ Main function to process the EPG data """
    # Load the master channel list from the external file
    master_channels = load_master_channels("master_channels.txt")

    # Example EPG sources to process (you can replace with actual file paths)
    epg_files = [
        "epgshare01/epg_ripper_US2.xml.gz", 
        "open-epg/egypt1.xml.gz",
        "iptv-epg/epg-in.xml.gz",
        "epgshare01/epg_ripper_US_LOCALS1.txt"
    ]

    # List to hold filtered channels
    all_filtered_channels = []
    log_data = ""

    # Loop through all XML files and process them
    for epg_file in epg_files:
        filtered_channels, log_msg = parse_and_filter_channels(master_channels, epg_file)
        all_filtered_channels.extend(filtered_channels)
        log_data += f"\n{log_msg}"

    # Write the filtered channels to the merged file
    merged_file = write_merged_file(all_filtered_channels)

    # Calculate the file size
    file_size = os.path.getsize(merged_file) / (1024 * 1024)  # File size in MB
    channels_count = len(all_filtered_channels)
    programs_count = len(all_filtered_channels)  # Adjust this as per the logic for programs

    # Update the index.html with the new values
    update_index_page(channels_count, programs_count, file_size, log_data)

if __name__ == "__main__":
    process_epg_data()

