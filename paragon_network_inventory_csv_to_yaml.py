#!/usr/bin/env python3
"""
CSV to YAML Router Configuration Converter
Converts device CSV into YAML format with r0, r1, r2... rN router entries.
"""

import csv
import yaml
import sys
from pathlib import Path


def convert_csv_to_yaml(csv_file, output_file=None, default_username='xxx', default_password='xxx'):
    """
    Convert CSV device list to YAML router configuration.
    
    Args:
        csv_file (str): Path to input CSV file
        output_file (str): Path to output YAML file (optional)
        default_username (str): Default username for all routers
        default_password (str): Default password for all routers
    
    Returns:
        dict: Dictionary containing routers configuration
    """
    
    # Read CSV file
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            devices = list(reader)
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)
    
    if not devices:
        print("Error: No devices found in CSV file.")
        sys.exit(1)
    
    # Create router dictionary
    routers = {}
    
    for idx, device in enumerate(devices):
        router_id = f"r{idx}"
        
        # Extract fields from CSV
        ip = device.get('Management IP', '').strip('\"')
        name = device.get('Name', '').strip('\"')
        model = device.get('Model', '').strip('\"')
        site = device.get('Site', '').strip('\"')
        serial = device.get('Serial', '').strip('\"')
        software = device.get('Software Version', '').strip('\"')
        product = device.get('Product', '').strip('\"')
        
        # Build router configuration
        routers[router_id] = {
            'username': default_username,
            'password': default_password,
            'ip': ip,
            'name': name,
            'model': model,
            'site': site,
            'serial': serial,
            'software_version': software,
            'product': product
        }
    
    # Create final structure
    config = {
        'routers': routers
    }
    
    # Convert to YAML
    yaml_output = yaml.dump(
        config,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True
    )
    
    # Write to file if output_file specified
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(yaml_output)
            print(f"✓ YAML configuration saved to: {output_file}")
        except Exception as e:
            print(f"Error writing to output file: {e}")
            sys.exit(1)
    
    return config, yaml_output


def print_summary(routers):
    """Print summary of routers created."""
    print("\n" + "="*70)
    print("ROUTER CONFIGURATION SUMMARY")
    print("="*70)
    print(f"{'Router ID':<10} {'Name':<30} {'IP Address':<15} {'Site':<20}")
    print("-"*70)
    
    for router_id, config in routers.items():
        print(f"{router_id:<10} {config['name']:<30} {config['ip']:<15} {config['site']:<20}")
    
    print("-"*70)
    print(f"Total routers: {len(routers)}")
    print(f"Default Credentials: xxx / xxx")
    print("="*70)


def main():
    """Main function."""
    
    # Get input and output file paths
    if len(sys.argv) < 2:
        print("Usage: python3 csv_to_yaml.py <input_csv> [output_yaml]")
        print("\nExample:")
        print("  python3 csv_to_yaml.py Devices-2.csv routers_output.yaml")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # If no output file specified, create default name
    if not output_file:
        output_file = Path(csv_file).stem + '_routers.yaml'
    
    print(f"Converting CSV: {csv_file}")
    print(f"Output YAML: {output_file}\n")
    
    # Convert CSV to YAML
    config, yaml_output = convert_csv_to_yaml(
        csv_file, 
        output_file,
        default_username='xxx',
        default_password='xxx'
    )
    
    # Print summary
    print_summary(config['routers'])
    
    # Print first few lines of YAML
    print("\nGenerated YAML (first 30 lines):")
    print("-"*70)
    lines = yaml_output.split('\n')[:30]
    print('\n'.join(lines))
    print("-"*70)


if __name__ == '__main__':
    main()
