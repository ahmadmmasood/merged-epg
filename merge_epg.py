import requests
import gzip
import xml.etree.ElementTree as ET
import os
from datetime import datetime
import pytz

# Load the master list of channels
def load_master_list():
    with open("master_channels.txt", "r") as f:
        # Read in all channels, ignoring lines that start with "#" and making the matching case-insensitive
        master_channels = [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]
    return master_channels

# Fetch and parse the EPG data from the given URL
def fetch_and_parse_epg(url):
    try:
        response = requests.get(url)
        response.raise_for_status()

        # If the URL contains "epgshare01", try the .txt file first
        if "epgshare01" in url:
            txt_url = url.replace(".xml.gz", ".txt")  # Replace .xml.gz with .txt
            print(f"Trying to fetch TXT file: {txt_url}")
            txt_response = requests.get(txt_url)
            if txt_response.status_code == 200:
                print(f"Successfully fetched TXT file from {txt_url}")
                file_content = txt_response.text
                print("TXT content preview (first 200 chars):", file_content[:200])  # Print preview of content
                return file_content, 'txt', txt_url  # Return the content and indicate it's a .txt file
            else:
                print(f"TXT file not available, falling back to XML: {url}")
                file_content = gzip.decompress(response.content).decode('utf-8')
                print("XML content preview (first 200 chars):", file_content[:200])  # Print preview of content
                return file_content, 'xml', url  # Return content and indicate it's an .xml file
        else:
            # If not epgshare01, always process the .xml.gz file
            file_content = gzip.decompress(response.content).decode('utf-8')
            print("XML content preview (first 200 chars):", file_content[:200])  # Print preview of content
            return file_content, 'xml', url  # Indicate it's an .xml file
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching/parsing {url}: {e}")
        return None, None, None

# Parse the XML data and match channels from the master list
def parse_xml(epg_content, channels):
    found_channels = []
    tree = ET.ElementTree(ET.fromstring(epg_content))
    root = tree.getroot()

    for channel in root.iter('channel'):
        # Use .text.strip() to handle extra spaces and make it case-insensitive
        channel_name = channel.find('display-name').text.strip().lower()
        if channel_name in channels:
            found_channels.append(channel_name)
    
    return found_channels

# Parse the TXT data and match channels from the master list
def parse_txt(epg_content, channels):
    found_channels = []
    for line in epg_content.splitlines():
        # Clean up each line and check for matches
        channel_name = line.strip().lower()
        if channel_name in channels:
            found_channels.append(channel_name)
    return found_channels

# Update the index.html page with the results
def update_index_page(channels_count, programs_count, file_size, log_data, analysis_data):
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
        <table border="1">
            <thead>
                <tr>
                    <th>Source URL</th>
                    <th>File Type</th>
                    <th>Status</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
                {log_data}
            </tbody>
        </table>
    </div>

    <h2>Channel Analysis:</h2>
    <button onclick="document.getElementById('analysis').style.display='block'">Show Analysis</button>
    <button onclick="document.getElementById('analysis').style.display='none'">Hide Analysis</button>
    <div id="analysis" style="display:none;">
        <pre>{analysis_data}</pre>
    </div>
    
    </body>
    </html>
    """

    # Write the content to the index.html file
    with open("index.html", "w") as file:
        file.write(html_content)
    
    print("index.html has been updated.")

# Main function to process all the EPG sources and match channels
def main():
    epg_sources = [
        'https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz',
        'https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz',
        'https://iptv-epg.org/files/epg-eg.xml.gz',
        'https://iptv-epg.org/files/epg-in.xml.gz',
        'https://iptv-epg.org/files/epg-lb.xml.gz',
        'https://www.open-epg.com/files/egypt1.xml.gz',
        'https://www.open-epg.com/files/egypt2.xml.gz',
        'https://www.open-epg.com/files/india3.xml.gz'
    ]

    # Load the master channel list
    master_channels = load_master_list()
    
    total_channels = len(master_channels)
    found_channels = 0
    found_programs = 0
    total_logs = []

    for url in epg_sources:
        epg_content, file_type, url = fetch_and_parse_epg(url)

        if epg_content:
            if file_type == 'xml':
                found = parse_xml(epg_content, master_channels)
            else:
                found = parse_txt(epg_content, master_channels)

            # Update count of found channels
            found_channels += len(found)
            total_logs.append(f"<tr><td>{url}</td><td>{file_type.upper()}</td><td>Success</td><td>Found {len(found)} channels</td></tr>")
            
            # To calculate programs found, extend this part
            found_programs += len(found)  # Placeholder; replace with actual program extraction if needed

        else:
            total_logs.append(f"<tr><td>{url}</td><td>Unknown</td><td>Error</td><td>Failed to fetch or parse</td></tr>")
    
    # Generate channel analysis text
    analysis_data = f"""
    Total Channels in Master List: {total_channels}
    Channels Found: {found_channels}
    Channels Not Found: {total_channels - found_channels}
    """

    # Update the index page with the results
    update_index_page(found_channels, found_programs, 37.00, '\n'.join(total_logs), analysis_data)

if __name__ == "__main__":
    main()

