#!/usr/bin/env python3
"""
Refactored Junos PyEZ Library for Device Configuration Automation (Class-based Architecture)

This module provides a clean, object-oriented approach to Junos device management
with classes for configuration, device management, P2P link configuration, and orchestration.
"""

import pdb
import yaml
import sys
import inspect
import json
import random
import ipaddress
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.exception import ConnectError, ConfigLoadError, CommitError
from yaml_flattener_with_access import yaml_to_flattened_database
from flatjson2vars import load_flattened_json


class ConfigManager:
    """Handles YAML configuration file operations"""
    
    @staticmethod
    def read_yaml_config(yaml_file):
        """
        Read device credentials from YAML file.
        
        Args:
            yaml_file (str): Path to YAML configuration file
            
        Returns:
            dict: Parsed YAML configuration
        """
        try:
            print(f"loading '{yaml_file}' as YAML inside function: {inspect.currentframe().f_code.co_name}")
            with open(yaml_file, 'r') as f:
                config = yaml.safe_load(f)
            print(f"dumping the data ...")
            yaml_str = yaml.dump(config)
            print(yaml_str)
            print(f"Done w/ dumping the data ...")
            return config
        except FileNotFoundError:
            print(f"Error: Configuration file '{yaml_file}' not found.")
            raise
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            raise


class JunosDeviceManager:
    """Manages Junos device connections and basic operations"""
    
    @staticmethod
    def connect(host, user, password):
        """
        Establish connection to Junos device.
        
        Args:
            host (str): Device IP address or hostname
            user (str): Username for authentication
            password (str): Password for authentication
            
        Returns:
            Device: Connected PyEZ Device object
        """
        try:
            dev = Device(host=host, user=user, passwd=password, port=22)
            dev.open()
            print(f"Successfully connected to {host}")
            return dev
        except ConnectError as e:
            print(f"Unable to connect to device: {e}")
            raise
    
    @staticmethod
    def close(dev):
        """
        Close connection to Junos device.
        
        Args:
            dev (Device): PyEZ Device object
        """
        dev.close()
        print(f"\nConnection closed")
    
    @staticmethod
    def get_version(dev):
        """
        Retrieve and display Junos version information.
        
        Args:
            dev (Device): Connected PyEZ Device object
            
        Returns:
            str: Junos version string
        """
        version = dev.facts.get('version')
        model = dev.facts.get('model')
        hostname = dev.facts.get('hostname')
        print(f"\nDevice Information:")
        print(f" Hostname: {hostname}")
        print(f" Model: {model}")
        print(f" Junos Version: {version}")
        return version


class P2PLinkConfigurator:
    """Handles point-to-point link configuration with LLDP discovery"""
    
    @staticmethod
    def configure_p2p_link(yaml_config_file, router1_name, router2_name, dev1, dev2, ip_address=None, group_name="P2P_CONFIG"):
        """
        Modular LLDP-based point-to-point link setup for two Junos routers.
        Determines actual physical connection by querying LLDP neighbors from live devices.
        
        Args:
            yaml_config_file (str): Path to YAML configuration file
            router1_name (str): Name of first router (e.g., 'r0')
            router2_name (str): Name of second router (e.g., 'r1')
            dev1 (Device): Connected PyEZ Device object for router1
            dev2 (Device): Connected PyEZ Device object for router2
            ip_address (str, optional): Base IP address for /31 link
            group_name (str): Configuration group name (default: "P2P_CONFIG")
            
        Returns:
            dict: Dictionary containing configuration status and details
        """
        print("\n" + "="*80)
        print(f"Starting Point-to-Point Link Configuration")
        print(f"Between: {router1_name} <--> {router2_name}")
        print("="*80)
        
        # Get actual chassis IDs from devices
        print(f"\nRetrieving chassis IDs from devices...")
        dev1_chassis = dev1.facts.get('serialnumber', '').lower()
        dev2_chassis = dev2.facts.get('serialnumber', '').lower()
        
        if not dev1_chassis:
            try:
                result = dev1.rpc.get_chassis_inventory()
                dev1_chassis = result.findtext('.//serial-number').lower()
            except:
                pass
        
        if not dev2_chassis:
            try:
                result = dev2.rpc.get_chassis_inventory()
                dev2_chassis = result.findtext('.//serial-number').lower()
            except:
                pass
        
        print(f" {router1_name} chassis ID: {dev1_chassis}")
        print(f" {router2_name} chassis ID: {dev2_chassis}")
        
        if not dev1_chassis or not dev2_chassis:
            print(" ✗ Could not retrieve chassis IDs from devices")
            return {"success": False, "error": "Failed to retrieve chassis IDs"}
        
        # Query actual LLDP neighbors from dev1
        print(f"\nQuerying LLDP neighbors from {router1_name}...")
        dev1_interface = None
        
        try:
            lldp_neighbors = dev1.rpc.get_lldp_neighbors_information()
            for neighbor in lldp_neighbors.findall('.//lldp-neighbor-information'):
                local_port = neighbor.findtext('.//lldp-local-port-id', '').strip()
                local_parent = neighbor.findtext('.//lldp-local-parent-interface-name', '').strip()
                remote_chassis = neighbor.findtext('.//lldp-remote-chassis-id', '').strip().lower()
                remote_port = neighbor.findtext('.//lldp-remote-port-id', '').strip()
                remote_system = neighbor.findtext('.//lldp-remote-system-name', '').strip()
                
                print(f" Checking: {local_port} -> Remote chassis: {remote_chassis}")
                
                # Check if remote chassis matches dev2's chassis
                if remote_chassis and (remote_chassis == dev2_chassis or dev2_chassis in remote_chassis):
                    dev1_interface = {
                        'name': local_parent if local_parent else local_port,
                        'local_port': local_port,
                        'local_parent': local_parent,
                        'remote_system': remote_system,
                        'remote_port': remote_port,
                        'remote_chassis_id': remote_chassis
                    }
                    print(f" ✓ Found connection on {router1_name}: {dev1_interface['name']}")
                    print(f" Remote system: {dev1_interface['remote_system']}")
                    print(f" Remote port: {dev1_interface['remote_port']}")
                    print(f" Remote chassis: {dev1_interface['remote_chassis_id']}")
                    break
            
            if not dev1_interface:
                print(f" ✗ No LLDP connection found from {router1_name} to {router2_name}")
                return {"success": False, "error": f"No LLDP connection found from {router1_name} to {router2_name}"}
        
        except Exception as e:
            print(f" ✗ Error querying LLDP from {router1_name}: {e}")
            return {"success": False, "error": f"LLDP query failed on {router1_name}: {e}"}
        
        # Query actual LLDP neighbors from dev2
        print(f"\nQuerying LLDP neighbors from {router2_name}...")
        dev2_interface = None
        
        try:
            lldp_neighbors = dev2.rpc.get_lldp_neighbors_information()
            for neighbor in lldp_neighbors.findall('.//lldp-neighbor-information'):
                local_port = neighbor.findtext('.//lldp-local-port-id', '').strip()
                local_parent = neighbor.findtext('.//lldp-local-parent-interface-name', '').strip()
                remote_chassis = neighbor.findtext('.//lldp-remote-chassis-id', '').strip().lower()
                remote_port = neighbor.findtext('.//lldp-remote-port-id', '').strip()
                remote_system = neighbor.findtext('.//lldp-remote-system-name', '').strip()
                
                print(f" Checking: {local_port} -> Remote chassis: {remote_chassis}")
                
                # Check if remote chassis matches dev1's chassis
                if remote_chassis and (remote_chassis == dev1_chassis or dev1_chassis in remote_chassis):
                    dev2_interface = {
                        'name': local_parent if local_parent else local_port,
                        'local_port': local_port,
                        'local_parent': local_parent,
                        'remote_system': remote_system,
                        'remote_port': remote_port,
                        'remote_chassis_id': remote_chassis
                    }
                    print(f" ✓ Found connection on {router2_name}: {dev2_interface['name']}")
                    print(f" Remote system: {dev2_interface['remote_system']}")
                    print(f" Remote port: {dev2_interface['remote_port']}")
                    print(f" Remote chassis: {dev2_interface['remote_chassis_id']}")
                    break
            
            if not dev2_interface:
                print(f" ✗ No LLDP connection found from {router2_name} to {router1_name}")
                return {"success": False, "error": f"No LLDP connection found from {router2_name} to {router1_name}"}
        
        except Exception as e:
            print(f" ✗ Error querying LLDP from {router2_name}: {e}")
            return {"success": False, "error": f"LLDP query failed on {router2_name}: {e}"}
        
        # Verify bidirectional connectivity
        print(f"\nVerifying bidirectional connectivity...")
        print(f" {router1_name} interface {dev1_interface['name']} connects to chassis {dev1_interface['remote_chassis_id']}")
        print(f" {router2_name} interface {dev2_interface['name']} connects to chassis {dev2_interface['remote_chassis_id']}")
        
        # Check if the remote chassis IDs match
        if not (dev2_chassis in dev1_interface['remote_chassis_id'] or dev1_interface['remote_chassis_id'] in dev2_chassis):
            print(f" ✗ Chassis ID mismatch on {router1_name}!")
            return {"success": False, "error": "Chassis ID verification failed"}
        
        if not (dev1_chassis in dev2_interface['remote_chassis_id'] or dev2_interface['remote_chassis_id'] in dev1_chassis):
            print(f" ✗ Chassis ID mismatch on {router2_name}!")
            return {"success": False, "error": "Chassis ID verification failed"}
        
        print(" ✓ Connection verified successfully!")
        
        # Generate or use specified IP address
        if ip_address is None:
            # Generate random /31 IP address
            octets = [random.randint(10, 200), random.randint(0, 255), random.randint(0, 255)]
            last_octet = random.randint(0, 254) & 0xFE  # Make it even
            ip_dev1 = f"{octets[0]}.{octets[1]}.{octets[2]}.{last_octet}/31"
            ip_dev2 = f"{octets[0]}.{octets[1]}.{octets[2]}.{last_octet + 1}/31"
        else:
            # Parse provided IP address
            try:
                network = ipaddress.IPv4Network(ip_address, strict=False)
                if network.prefixlen != 31:
                    print(f" ✗ IP address must be /31, got /{network.prefixlen}")
                    return {"success": False, "error": "IP address must be /31"}
                
                hosts = list(network.hosts())
                if len(hosts) != 2:
                    ip_dev1 = f"{network.network_address}/31"
                    ip_dev2 = f"{network.broadcast_address}/31"
                else:
                    ip_dev1 = f"{hosts[0]}/31"
                    ip_dev2 = f"{hosts[1]}/31"
            except Exception as e:
                print(f" ✗ Invalid IP address format: {e}")
                return {"success": False, "error": f"Invalid IP address: {e}"}
        
        print(f"\nIP Address Assignment:")
        print(f" {router1_name} ({dev1_interface['name']}): {ip_dev1}")
        print(f" {router2_name} ({dev2_interface['name']}): {ip_dev2}")
        
        # Prepare configurations
        config_dev1 = [
            f"set groups {group_name} interfaces {dev1_interface['name']} unit 0 description \"P2P to {router2_name} {dev2_interface['name']}\"",
            f"set groups {group_name} interfaces {dev1_interface['name']} unit 0 family inet address {ip_dev1}"
        ]
        
        config_dev2 = [
            f"set groups {group_name} interfaces {dev2_interface['name']} unit 0 description \"P2P to {router1_name} {dev1_interface['name']}\"",
            f"set groups {group_name} interfaces {dev2_interface['name']} unit 0 family inet address {ip_dev2}"
        ]
        
        print(f"\nConfiguration to be applied:")
        print(f"\n Router {router1_name}:")
        for cmd in config_dev1:
            print(f" {cmd}")
        print(f"\n Router {router2_name}:")
        for cmd in config_dev2:
            print(f" {cmd}")
        
        # Load configuration on both routers
        try:
            print(f"\nLoading configuration on {router1_name}...")
            cu_dev1 = Config(dev1)
            cu_dev1.lock()
            for cmd in config_dev1:
                cu_dev1.load(cmd, format='set')
            print(f" ✓ Configuration loaded on {router1_name}")
            
            print(f"\nLoading configuration on {router2_name}...")
            cu_dev2 = Config(dev2)
            cu_dev2.lock()
            for cmd in config_dev2:
                cu_dev2.load(cmd, format='set')
            print(f" ✓ Configuration loaded on {router2_name}")
            
            # Show diff for verification
            print(f"\n" + "-"*80)
            print(f"Configuration Diff for {router1_name}:")
            print("-"*80)
            print(cu_dev1.diff())
            
            print(f"\n" + "-"*80)
            print(f"Configuration Diff for {router2_name}:")
            print("-"*80)
            print(cu_dev2.diff())
            
            # Pause for admin approval
            print(f"\n" + "="*80)
            print("ADMIN APPROVAL REQUIRED")
            print("="*80)
            print("Please review the configuration changes above.")
            response = input("\nType 'yes' to commit, or anything else to rollback: ").strip().lower()
            
            if response == 'yes':
                print(f"\nCommitting configuration on {router1_name}...")
                cu_dev1.commit(comment=f"P2P link config via {group_name}")
                print(f" ✓ Configuration committed on {router1_name}")
                
                print(f"\nCommitting configuration on {router2_name}...")
                cu_dev2.commit(comment=f"P2P link config via {group_name}")
                print(f" ✓ Configuration committed on {router2_name}")
                
                # Unlock configurations
                cu_dev1.unlock()
                cu_dev2.unlock()
                print(f"\n ✓ Configurations unlocked")
                
                # Update YAML file
                print(f"\nUpdating YAML file: {yaml_config_file}")
                with open(yaml_config_file, 'r') as f:
                    yaml_data = yaml.safe_load(f)
                
                # Ensure routers exist in YAML
                if 'routers' not in yaml_data:
                    yaml_data['routers'] = {}
                
                if router1_name not in yaml_data['routers']:
                    yaml_data['routers'][router1_name] = {'interfaces': {}}
                if 'interfaces' not in yaml_data['routers'][router1_name]:
                    yaml_data['routers'][router1_name]['interfaces'] = {}
                
                if router2_name not in yaml_data['routers']:
                    yaml_data['routers'][router2_name] = {'interfaces': {}}
                if 'interfaces' not in yaml_data['routers'][router2_name]:
                    yaml_data['routers'][router2_name]['interfaces'] = {}
                
                # Add new interface configuration to router1
                new_interface_name_dev1 = f"p2p_{dev1_interface['name'].replace(':', '_').replace('/', '_')}"
                yaml_data['routers'][router1_name]['interfaces'][new_interface_name_dev1] = {
                    'physical_interface': dev1_interface['name'],
                    'ip_address': ip_dev1,
                    'description': f"P2P to {router2_name} {dev2_interface['name']}",
                    'connects_to': {
                        'router': router2_name,
                        'interface': dev2_interface['name']
                    },
                    'config_group': group_name,
                    'config': config_dev1
                }
                
                # Add new interface configuration to router2
                new_interface_name_dev2 = f"p2p_{dev2_interface['name'].replace(':', '_').replace('/', '_')}"
                yaml_data['routers'][router2_name]['interfaces'][new_interface_name_dev2] = {
                    'physical_interface': dev2_interface['name'],
                    'ip_address': ip_dev2,
                    'description': f"P2P to {router1_name} {dev1_interface['name']}",
                    'connects_to': {
                        'router': router1_name,
                        'interface': dev1_interface['name']
                    },
                    'config_group': group_name,
                    'config': config_dev2
                }
                
                # Write updated YAML
                with open(yaml_config_file, 'w') as f:
                    yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
                
                print(f" ✓ YAML file updated successfully")
                print(f" Added interface '{new_interface_name_dev1}' to {router1_name}")
                print(f" Added interface '{new_interface_name_dev2}' to {router2_name}")
                
                result = {
                    "success": True,
                    "router1_name": router1_name,
                    "router2_name": router2_name,
                    "router1_interface": dev1_interface['name'],
                    "router2_interface": dev2_interface['name'],
                    "router1_ip": ip_dev1,
                    "router2_ip": ip_dev2,
                    "group_name": group_name
                }
                
                print(f"\n" + "="*80)
                print("Configuration completed successfully!")
                print("="*80)
                return result
            else:
                print(f"\n ✗ Configuration rollback requested")
                cu_dev1.rollback()
                cu_dev1.unlock()
                cu_dev2.rollback()
                cu_dev2.unlock()
                print(" ✓ Configuration rolled back on both routers")
                return {"success": False, "error": "Configuration rejected by admin"}
        
        except Exception as e:
            print(f"\n ✗ Error during configuration: {e}")
            try:
                cu_dev1.unlock()
            except:
                pass
            try:
                cu_dev2.unlock()
            except:
                pass
            return {"success": False, "error": str(e)}


class JunosAutomationOrchestrator:
    """Orchestrates the complete automation workflow"""
    
    def __init__(self, yaml_config_file):
        """
        Initialize orchestrator with configuration file.
        
        Args:
            yaml_config_file (str): Path to YAML configuration file
        """
        self.yaml_config_file = yaml_config_file
        self.devr0 = None
        self.devr1 = None
    
    def run(self):
        """
        Execute the complete automation workflow:
        1. Read YAML configuration
        2. Connect to devices
        3. Get device versions
        4. Configure P2P link with LLDP discovery
        """
        try:
            # Step 1: Read YAML configuration
            print("Reading configuration file...")
            yaml_config = ConfigManager.read_yaml_config(self.yaml_config_file)
            
            # Step 2: Flatten YAML
            data = yaml_to_flattened_database(self.yaml_config_file, output_format='all')
            
            # Step 3: Load as dotdict
            config = load_flattened_json('yaml_flat.json', mode='dotdict')
            
            # Step 4: Get connection details
            print("\nExtracting connection details...")
            r0host = config.routers.r0.ip
            r1host = config.routers.r1.ip
            user = config.routers.r0.username
            password = config.routers.r0.password
            print(f"r0 IP: {r0host}")
            print(f"r1 IP: {r1host}")
            
            # Step 5: Connect to devices
            self.devr0 = JunosDeviceManager.connect(r0host, user, password)
            self.devr1 = JunosDeviceManager.connect(r1host, user, password)
            
            # Step 6: Get device versions
            JunosDeviceManager.get_version(self.devr0)
            JunosDeviceManager.get_version(self.devr1)
            
            # Step 7: Configure P2P link using LLDP discovery
            print("\n" + "="*80)
            print("Starting P2P Link Configuration with LLDP Discovery")
            print("="*80)
            
            # CORRECT CALL: Pass router names as strings, device objects as Device instances
            result = P2PLinkConfigurator.configure_p2p_link(
                yaml_config_file=self.yaml_config_file,
                router1_name='r0',  # String: router name
                router2_name='r1',  # String: router name
                dev1=self.devr0,    # Device object
                dev2=self.devr1,    # Device object
                ip_address=None,    # Or specify like "10.0.0.0/31"
                group_name='CORE_LINK'
            )
            
            if result["success"]:
                print(f"\n✓ P2P link configured successfully!")
                print(f" {result['router1_name']} interface: {result['router1_interface']} - {result['router1_ip']}")
                print(f" {result['router2_name']} interface: {result['router2_interface']} - {result['router2_ip']}")
                print(f" Configuration group: {result['group_name']}")
            else:
                print(f"\n✗ P2P link configuration failed: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Step 8: Close connections
            if self.devr0:
                JunosDeviceManager.close(self.devr0)
            if self.devr1:
                JunosDeviceManager.close(self.devr1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python script.py <config_file.yaml>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    print(f"Loading configuration from: {config_file}")
    
    orchestrator = JunosAutomationOrchestrator(config_file)
    orchestrator.run()
