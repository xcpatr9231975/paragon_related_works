#!/usr/bin/env python3
"""
LLDP to YAML Interface Updater

This script extracts local interface information from an LLDP JSON file
and adds them to the corresponding router in a YAML configuration file.

Usage:
    python update_router_interfaces.py <lldp_json_file> <yaml_file>

Example:
    python update_router_interfaces.py lldp_neighbors_10_161_32_178_20251114_214518.json advanced_routers.yaml
"""

import json
import yaml
import re
import sys
from pathlib import Path


def extract_ip_from_filename(filename):
    """
    Extract IP address from filename.

    Example: lldp_neighbors_10_161_32_178_20251114_214518.json -> 10.161.32.178
    """
    # Pattern to match IP address in filename
    pattern = r'(\d{1,3}[_\.]\d{1,3}[_\.]\d{1,3}[_\.]\d{1,3})'
    match = re.search(pattern, filename)

    if match:
        ip_string = match.group(1)
        # Replace underscores with dots
        ip_address = ip_string.replace('_', '.')
        return ip_address
    return None


def find_router_by_ip(routers_data, target_ip):
    """
    Find which router (r0, r1, r2, etc.) has the given IP address.

    Args:
        routers_data: Dictionary containing router configurations
        target_ip: IP address to search for

    Returns:
        Router key (e.g., 'r0', 'r1') or None if not found
    """
    for router_key, router_config in routers_data.items():
        if router_config.get('ip') == target_ip:
            return router_key
    return None


def load_lldp_data(json_file):
    """Load LLDP neighbor data from JSON file."""
    with open(json_file, 'r') as f:
        return json.load(f)


def load_yaml_data(yaml_file):
    """Load router configuration from YAML file."""
    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)


def create_interface_entry(interface_name, lldp_entry):
    """
    Create a new interface entry based on LLDP data.

    Args:
        interface_name: Name of the local interface
        lldp_entry: LLDP neighbor information

    Returns:
        Dictionary containing interface configuration
    """
    interface_data = {
        'name': interface_name,
        'local_parent': lldp_entry.get('local_parent', '-'),
        'remote_system': lldp_entry.get('remote_system_name', 'Unknown'),
        'remote_port': lldp_entry.get('remote_port_description', 'Unknown'),
        'remote_chassis_id': lldp_entry.get('remote_chassis_id', 'Unknown')
    }

    return interface_data


def add_interfaces_to_router(routers_data, router_key, lldp_data):
    """
    Add or update interfaces section for the specified router.

    Args:
        routers_data: Dictionary containing all router configurations
        router_key: The router to update (e.g., 'r0', 'r1')
        lldp_data: List of LLDP neighbor entries

    Returns:
        Updated routers_data dictionary
    """
    if router_key not in routers_data:
        print(f"Error: Router {router_key} not found in YAML data")
        return routers_data

    # Get existing interfaces or create new dict
    if 'interfaces' not in routers_data[router_key]:
        routers_data[router_key]['interfaces'] = {}

    interfaces = routers_data[router_key]['interfaces']

    # Add each local interface from LLDP data
    for idx, lldp_entry in enumerate(lldp_data):
        local_interface = lldp_entry.get('local_interface')

        if not local_interface:
            continue

        # Create a unique interface key
        interface_key = f"lldp_{local_interface.replace(':', '_').replace('/', '_')}"

        # Create interface entry
        interface_data = create_interface_entry(local_interface, lldp_entry)

        # Add to interfaces
        interfaces[interface_key] = interface_data

    return routers_data


def save_yaml_data(data, output_file):
    """Save updated router configuration to YAML file."""
    with open(output_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python update_router_interfaces.py <lldp_json_file> <yaml_file>")
        print("Example: python update_router_interfaces.py lldp_neighbors_10_161_32_178_20251114_214518.json advanced_routers.yaml")
        sys.exit(1)

    json_file = sys.argv[1]
    yaml_file = sys.argv[2]

    # Validate input files exist
    if not Path(json_file).exists():
        print(f"Error: JSON file '{json_file}' not found")
        sys.exit(1)

    if not Path(yaml_file).exists():
        print(f"Error: YAML file '{yaml_file}' not found")
        sys.exit(1)

    # Extract IP from filename
    target_ip = extract_ip_from_filename(json_file)
    if not target_ip:
        print(f"Error: Could not extract IP address from filename '{json_file}'")
        sys.exit(1)

    print(f"Extracted IP address from filename: {target_ip}")

    # Load data
    lldp_data = load_lldp_data(json_file)
    yaml_data = load_yaml_data(yaml_file)

    # Get routers section
    if 'routers' not in yaml_data:
        print("Error: 'routers' key not found in YAML file")
        sys.exit(1)

    routers = yaml_data['routers']

    # Find which router has this IP
    router_key = find_router_by_ip(routers, target_ip)

    if not router_key:
        print(f"Error: No router found with IP address {target_ip}")
        print(f"Available routers:")
        for key, config in routers.items():
            print(f"  {key}: {config.get('ip', 'No IP')}")
        sys.exit(1)

    print(f"Found router: {router_key} (IP: {target_ip})")
    print(f"Adding {len(lldp_data)} interfaces from LLDP data...")

    # Add interfaces to the router
    yaml_data['routers'] = add_interfaces_to_router(routers, router_key, lldp_data)

    # Create output filename
    yaml_path = Path(yaml_file)
    output_file = yaml_path.stem + "_updated" + yaml_path.suffix

    # Save updated YAML
    save_yaml_data(yaml_data, output_file)

    print(f"\nSuccess! Updated YAML saved to: {output_file}")
    print(f"Router '{router_key}' now has {len(yaml_data['routers'][router_key]['interfaces'])} interfaces")


if __name__ == "__main__":
    main()
