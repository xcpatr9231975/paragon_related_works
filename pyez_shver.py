#!/usr/bin/env python3
"""
Basic Junos PyEZ script to show device version and exit
"""

from jnpr.junos import Device

def show_version(host, username, password):
    """
    Connect to Junos device, display version, and exit.

    Args:
        host (str): Device IP address or hostname
        username (str): Username for authentication
        password (str): Password for authentication
    """
    # Connect to device
    dev = Device(host=host, user=username, passwd=password, port=22)

    try:
        # Open connection
        dev.open()
        print(f"Connected to {host}")

        # Get and display version information
        print(f"\nHostname: {dev.facts['hostname']}")
        print(f"Model: {dev.facts['model']}")
        print(f"Junos Version: {dev.facts['version']}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close connection
        dev.close()
        print("\nConnection closed")


if __name__ == '__main__':
    # Device credentials
    HOST = '10.161.32.178'
    USERNAME = 'jnpr'
    PASSWORD = 'pass123'

    # Run the function
    show_version(HOST, USERNAME, PASSWORD)
