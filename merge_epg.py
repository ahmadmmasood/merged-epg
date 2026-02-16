import requests
import gzip
import io
import xml.etree.ElementTree as ET

# List of EPG URLs
epg_urls = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

# Function to download and extract XML from URL
def download_and_extract(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        
        # Decompress the gzipped content
        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
            return f.read().decode('utf-8')  # Return the decompressed XML content as string
    
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return None

# Function to process the XML data
def process_xml(xml_content):
    try:
        root = ET.fromstring(xml_content)
        channels = []
        
        # Assuming XML has 'channel' and 'program' elements. Adjust this based on actual XML structure.
        for channel in root.findall('.//channel'):  # Modify based on XML structure
            channel_name = channel.find('display-name').text.lower()  # Case-insensitive check
            channels.append(channel_name)
        
        return channels
    except ET.ParseError as e:
        print(f"Error parsing XML content: {e}")
        return []

# Download and process each EPG URL
channels_found = []
for url in epg_urls:
    xml_content = download_and_extract(url)
    if xml_content:
        channels = process_xml(xml_content)
        channels_found.extend(channels)
    else:
        print(f"Failed to process {url}")

# Filter channels based on your master list (case insensitive)
with open('master_channels.txt', 'r') as file:
    master_channels = [line.strip().lower() for line in file.readlines()]

# Filter the channels found
filtered_channels = [ch for ch in channels_found if ch in master_channels]

# Output results
print(f"Channels matched: {len(filtered_channels)}")
for channel in filtered_channels:
    print(channel)

