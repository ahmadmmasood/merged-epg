import gzip
import xml.etree.ElementTree as ET
import os

# Function to read channels from the master_channels.txt file
def read_channels_from_file(file_path):
    channels = {
        "premium": [],
        "basic": [],
        "local": [],
        "regional": [],
        "foreign": []  # This will handle the Foreign Tier
    }
    current_category = None

    with open(file_path, "r") as file:
        for line in file:
            line = line.strip()
            if "PREMIUM TIER" in line:
                current_category = "premium"
            elif "BASIC / EXPANDED BASIC" in line:
                current_category = "basic"
            elif "LOCAL CHANNELS" in line:
                current_category = "local"
            elif "REGIONAL NETWORKS" in line:
                current_category = "regional"
            elif "FOREIGN TIER" in line:
                current_category = "foreign"
            elif line and not line.startswith("="):
                channels[current_category].append(line)

    return channels

# File path to the master channel list
channels_file = "master_channels.txt"

# Read channels from file
channels = read_channels_from_file(channels_file)

# Filter out any channels that mention "Pacific" or are considered West Coast channels
def filter_west_coast(channels):
    return {category: [ch for ch in channel_list if "Pacific" not in ch] for category, channel_list in channels.items()}

channels = filter_west_coast(channels)

# Create the XML structure
root = ET.Element("channels")

# Function to add channels to the XML
def add_channels(channel_list, tier):
    for channel in channel_list:
        channel_element = ET.SubElement(root, "channel")
        channel_element.set("tier", tier)
        channel_element.text = channel

# Add all channels to XML structure
add_channels(channels["premium"], "Premium Tier")
add_channels(channels["basic"], "Basic Tier")
add_channels(channels["local"], "Local Channels")
add_channels(channels["regional"], "Regional Networks")
add_channels(channels["foreign"], "Foreign Tier")  # Add Foreign Tier channels

# Create the tree and save as XML
tree = ET.ElementTree(root)

# Save XML as .xml file
xml_filename = "channels.xml"
tree.write(xml_filename)

# Compress the XML file into .gz
with open(xml_filename, "rb") as f_in:
    with gzip.open(f"{xml_filename}.gz", "wb") as f_out:
        f_out.writelines(f_in)

# Clean up the original XML after gzipping
os.remove(xml_filename)

print(f"XML file with channels has been created and compressed into {xml_filename}.gz")

