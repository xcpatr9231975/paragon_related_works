#!/usr/bin/env python3
"""
Comprehensive Junos PyEZ Library for Multi-Router Configuration Automation

This module provides a scalable, object-oriented approach to managing multiple
Junos devices (1 to N routers) with dynamic discovery and P2P link configuration.
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
    
    @staticmethod
    def discover_routers(yaml_config):
        """
        Dynamically discover all routers in YAML configuration.
        
        Args:
            yaml_config (dict): Parsed YAML configuration
            
        Returns:
            list: List of router names (e.g., ['r0', 'r1', 'r2'])
        """
        if 'routers' not in yaml_config:
            return []
        
        router_names = [key for key in yaml_config['routers'].keys() 
                       if isinstance(yaml_config['routers'][key], dict)]
        
        print(f"\nDiscovered {len(router_names)} router(s): {', '.join(router_names)}")
        return sorted(router_names)  # Sort to ensure consistent ordering
    
    @staticmethod
    def get_router_config(config, router_name):
        """
        Extract configuration for a specific router.
        
        Args:
            config: Flattened dotdict configuration object
            router_name (str): Name of router (e.g., 'r0')
            
        Returns:
            dict: Router configuration containing ip, username, password, etc.
        """
        try:
            router = getattr(config.routers, router_name)
            return {
                'name': router_name,
                'ip': router.ip,
                'username': router.username,
                'password': router.password,
                'chassis': getattr(router, 'chassis', None),
                'hostname': getattr(router, 'name', None)
            }
        except AttributeError as e:
            print(f"Error: Missing configuration for router '{router_name}': {e}")
            return None


class JunosDeviceManager:
    """Manages Junos device connections and basic operations"""
    
    def __init__(self):
        """Initialize device manager with empty device registry"""
        self.devices = {}  # Dictionary to store connected devices
    
    def connect(self, router_name, host, user, password):
        """
        Establish connection to Junos device and store in registry.
        
        Args:
            router_name (str): Logical name (e.g., 'r0')
            host (str): Device IP address or hostname
            user (str): Username for authentication
            password (str): Password for authentication
            
        Returns:
            Device: Connected PyEZ Device object
        """
        try:
            dev = Device(host=host, user=user, passwd=password, port=22)
            dev.open()
            self.devices[router_name] = dev
            print(f"✓ Successfully connected to {router_name} ({host})")
            return dev
        except ConnectError as e:
            print(f"✗ Unable to connect to {router_name} ({host}): {e}")
            return None
    
    def connect_all(self, router_configs):
        """
        Connect to multiple routers.
        
        Args:
            router_configs (list): List of router configuration dicts
            
        Returns:
            dict: Dictionary of {router_name: Device} for successful connections
        """
        print(f"\n{'='*80}")
        print(f"Connecting to {len(router_configs)} router(s)...")
        print(f"{'='*80}")
        
        for router_config in router_configs:
            self.connect(
                router_config['name'],
                router_config['ip'],
                router_config['username'],
                router_config['password']
            )
        
        successful = len([d for d in self.devices.values() if d is not None])
        print(f"\n✓ Successfully connected to {successful}/{len(router_configs)} router(s)")
        return self.devices
    
    def close(self, router_name):
        """
        Close connection to specific Junos device.
        
        Args:
            router_name (str): Name of router to disconnect
        """
        if router_name in self.devices and self.devices[router_name]:
            self.devices[router_name].close()
            print(f"✓ Connection closed: {router_name}")
            self.devices[router_name] = None
    
    def close_all(self):
        """Close all device connections"""
        print(f"\n{'='*80}")
        print("Closing all connections...")
        print(f"{'='*80}")
        
        for router_name in list(self.devices.keys()):
            self.close(router_name)
    
    def get_version(self, dev, router_name):
        """
        Retrieve and display Junos version information.
        
        Args:
            dev (Device): Connected PyEZ Device object
            router_name (str): Name of router for display
            
        Returns:
            str: Junos version string
        """
        if not dev:
            print(f"✗ No connection for {router_name}")
            return None
        
        version = dev.facts.get('version')
        model = dev.facts.get('model')
        hostname = dev.facts.get('hostname')
        serial = dev.facts.get('serialnumber')
        
        print(f"\n{router_name} Device Information:")
        print(f"  Hostname: {hostname}")
        print(f"  Model: {model}")
        print(f"  Serial: {serial}")
        print(f"  Junos Version: {version}")
        
        return version
    
    def get_all_versions(self):
        """Get version information for all connected devices"""
        print(f"\n{'='*80}")
        print("Device Version Information")
        print(f"{'='*80}")
        
        for router_name, dev in self.devices.items():
            if dev:
                self.get_version(dev, router_name)


class P2PLinkConfigurator:
    """Handles point-to-point link configuration with LLDP discovery"""
    
    @staticmethod
    def configure_p2p_link(yaml_config_file, router1_name, router2_name, dev1, dev2, 
                          ip_address=None, group_name="P2P_CONFIG"):
        """
        Modular LLDP-based point-to-point link setup for two Junos routers.
        
        Args:
            yaml_config_file (str): Path to YAML configuration file
            router1_name (str): Name of first router (e.g., 'r0')
            router2_name (str): Name of second router (e.g., 'r1')
            dev1 (Device): Connected PyEZ Device object for router1
            dev2 (Device): Connected PyEZ Device object for router2
            ip_address (str, optional): Base IP address for /31 link
            group_name (str): Configuration group name
            
        Returns:
            dict: Configuration status and details
        """
        print("\n" + "="*80)
        print(f"P2P Link Configuration: {router1_name} <--> {router2_name}")
        print("="*80)
        
        if not dev1 or not dev2:
            print("✗ One or both devices not connected")
            return {"success": False, "error": "Device not connected"}
        
        # Get chassis IDs
        print(f"\nRetrieving chassis IDs...")
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
        
        print(f"  {router1_name} chassis: {dev1_chassis}")
        print(f"  {router2_name} chassis: {dev2_chassis}")
        
        if not dev1_chassis or not dev2_chassis:
            return {"success": False, "error": "Failed to retrieve chassis IDs"}
        
        # Query LLDP from router1
        print(f"\nQuerying LLDP from {router1_name}...")
        dev1_interface = None
        
        try:
            lldp_neighbors = dev1.rpc.get_lldp_neighbors_information()
            for neighbor in lldp_neighbors.findall('.//lldp-neighbor-information'):
                local_port = neighbor.findtext('.//lldp-local-port-id', '').strip()
                local_parent = neighbor.findtext('.//lldp-local-parent-interface-name', '').strip()
                remote_chassis = neighbor.findtext('.//lldp-remote-chassis-id', '').strip().lower()
                remote_port = neighbor.findtext('.//lldp-remote-port-id', '').strip()
                remote_system = neighbor.findtext('.//lldp-remote-system-name', '').strip()
                
                if remote_chassis and (remote_chassis == dev2_chassis or dev2_chassis in remote_chassis):
                    dev1_interface = {
                        'name': local_parent if local_parent else local_port,
                        'local_port': local_port,
                        'remote_system': remote_system,
                        'remote_port': remote_port,
                        'remote_chassis_id': remote_chassis
                    }
                    print(f"  ✓ Found: {dev1_interface['name']} -> {remote_system}")
                    break
            
            if not dev1_interface:
                return {"success": False, "error": f"No LLDP connection found from {router1_name} to {router2_name}"}
        except Exception as e:
            return {"success": False, "error": f"LLDP query failed on {router1_name}: {e}"}
        
        # Query LLDP from router2
        print(f"\nQuerying LLDP from {router2_name}...")
        dev2_interface = None
        
        try:
            lldp_neighbors = dev2.rpc.get_lldp_neighbors_information()
            for neighbor in lldp_neighbors.findall('.//lldp-neighbor-information'):
                local_port = neighbor.findtext('.//lldp-local-port-id', '').strip()
                local_parent = neighbor.findtext('.//lldp-local-parent-interface-name', '').strip()
                remote_chassis = neighbor.findtext('.//lldp-remote-chassis-id', '').strip().lower()
                remote_port = neighbor.findtext('.//lldp-remote-port-id', '').strip()
                remote_system = neighbor.findtext('.//lldp-remote-system-name', '').strip()
                
                if remote_chassis and (remote_chassis == dev1_chassis or dev1_chassis in remote_chassis):
                    dev2_interface = {
                        'name': local_parent if local_parent else local_port,
                        'local_port': local_port,
                        'remote_system': remote_system,
                        'remote_port': remote_port,
                        'remote_chassis_id': remote_chassis
                    }
                    print(f"  ✓ Found: {dev2_interface['name']} -> {remote_system}")
                    break
            
            if not dev2_interface:
                return {"success": False, "error": f"No LLDP connection found from {router2_name} to {router1_name}"}
        except Exception as e:
            return {"success": False, "error": f"LLDP query failed on {router2_name}: {e}"}
        
        # Verify bidirectional connectivity
        print(f"\n✓ Bidirectional link verified!")
        
        # Generate IP addresses
        if ip_address is None:
            octets = [random.randint(10, 200), random.randint(0, 255), random.randint(0, 255)]
            last_octet = random.randint(0, 254) & 0xFE
            ip_dev1 = f"{octets[0]}.{octets[1]}.{octets[2]}.{last_octet}/31"
            ip_dev2 = f"{octets[0]}.{octets[1]}.{octets[2]}.{last_octet + 1}/31"
        else:
            try:
                network = ipaddress.IPv4Network(ip_address, strict=False)
                if network.prefixlen != 31:
                    return {"success": False, "error": "IP address must be /31"}
                hosts = list(network.hosts())
                ip_dev1 = f"{hosts[0] if hosts else network.network_address}/31"
                ip_dev2 = f"{hosts[1] if len(hosts) > 1 else network.broadcast_address}/31"
            except Exception as e:
                return {"success": False, "error": f"Invalid IP: {e}"}
        
        print(f"\nIP Assignment:")
        print(f"  {router1_name} ({dev1_interface['name']}): {ip_dev1}")
        print(f"  {router2_name} ({dev2_interface['name']}): {ip_dev2}")
        
        # Prepare configurations
        config_dev1 = [
            f"set groups {group_name} interfaces {dev1_interface['name']} unit 0 description \"P2P to {router2_name} {dev2_interface['name']}\"",
            f"set groups {group_name} interfaces {dev1_interface['name']} unit 0 family inet address {ip_dev1}"
        ]
        
        config_dev2 = [
            f"set groups {group_name} interfaces {dev2_interface['name']} unit 0 description \"P2P to {router1_name} {dev1_interface['name']}\"",
            f"set groups {group_name} interfaces {dev2_interface['name']} unit 0 family inet address {ip_dev2}"
        ]
        
        # Load and commit configuration
        try:
            print(f"\nLoading configuration...")
            cu_dev1 = Config(dev1)
            cu_dev1.lock()
            for cmd in config_dev1:
                cu_dev1.load(cmd, format='set')
            
            cu_dev2 = Config(dev2)
            cu_dev2.lock()
            for cmd in config_dev2:
                cu_dev2.load(cmd, format='set')
            
            print(f"\n{'-'*80}")
            print(f"Config diff for {router1_name}:")
            print(f"{'-'*80}")
            print(cu_dev1.diff())
            
            print(f"\n{'-'*80}")
            print(f"Config diff for {router2_name}:")
            print(f"{'-'*80}")
            print(cu_dev2.diff())
            
            print(f"\n{'='*80}")
            print("ADMIN APPROVAL REQUIRED")
            print(f"{'='*80}")
            response = input("\nType 'yes' to commit, or anything else to rollback: ").strip().lower()
            
            if response == 'yes':
                cu_dev1.commit(comment=f"P2P link via {group_name}")
                cu_dev2.commit(comment=f"P2P link via {group_name}")
                cu_dev1.unlock()
                cu_dev2.unlock()
                
                print(f"\n✓ Configuration committed successfully!")
                
                # Update YAML
                with open(yaml_config_file, 'r') as f:
                    yaml_data = yaml.safe_load(f)
                
                if 'routers' not in yaml_data:
                    yaml_data['routers'] = {}
                
                for rname in [router1_name, router2_name]:
                    if rname not in yaml_data['routers']:
                        yaml_data['routers'][rname] = {}
                    if 'interfaces' not in yaml_data['routers'][rname]:
                        yaml_data['routers'][rname]['interfaces'] = {}
                
                # Add interfaces
                yaml_data['routers'][router1_name]['interfaces'][f"p2p_{dev1_interface['name'].replace(':', '_').replace('/', '_')}"] = {
                    'physical_interface': dev1_interface['name'],
                    'ip_address': ip_dev1,
                    'description': f"P2P to {router2_name} {dev2_interface['name']}",
                    'connects_to': {'router': router2_name, 'interface': dev2_interface['name']},
                    'config_group': group_name,
                    'config': config_dev1
                }
                
                yaml_data['routers'][router2_name]['interfaces'][f"p2p_{dev2_interface['name'].replace(':', '_').replace('/', '_')}"] = {
                    'physical_interface': dev2_interface['name'],
                    'ip_address': ip_dev2,
                    'description': f"P2P to {router1_name} {dev1_interface['name']}",
                    'connects_to': {'router': router1_name, 'interface': dev1_interface['name']},
                    'config_group': group_name,
                    'config': config_dev2
                }
                
                with open(yaml_config_file, 'w') as f:
                    yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
                
                return {
                    "success": True,
                    "router1_name": router1_name,
                    "router2_name": router2_name,
                    "router1_interface": dev1_interface['name'],
                    "router2_interface": dev2_interface['name'],
                    "router1_ip": ip_dev1,
                    "router2_ip": ip_dev2,
                    "group_name": group_name
                }
            else:
                cu_dev1.rollback()
                cu_dev1.unlock()
                cu_dev2.rollback()
                cu_dev2.unlock()
                return {"success": False, "error": "Configuration rejected"}
        
        except Exception as e:
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
    """Orchestrates complete automation workflow for multiple routers"""
    
    def __init__(self, yaml_config_file):
        """
        Initialize orchestrator.
        
        Args:
            yaml_config_file (str): Path to YAML configuration file
        """
        self.yaml_config_file = yaml_config_file
        self.device_manager = JunosDeviceManager()
        self.router_names = []
        self.router_configs = []
    
    def discover_and_connect(self):
        """
        Discover routers from YAML and connect to all of them.
        
        Returns:
            bool: True if at least one connection successful
        """
        print(f"\n{'='*80}")
        print("STEP 1: Discovery and Connection")
        print(f"{'='*80}")
        
        # Read YAML
        yaml_config = ConfigManager.read_yaml_config(self.yaml_config_file)
        
        # Discover routers
        self.router_names = ConfigManager.discover_routers(yaml_config)
        
        if not self.router_names:
            print("✗ No routers found in configuration file")
            return False
        
        # Flatten YAML
        data = yaml_to_flattened_database(self.yaml_config_file, output_format='all')
        config = load_flattened_json('yaml_flat.json', mode='dotdict')
        
        # Get router configurations
        self.router_configs = []
        for router_name in self.router_names:
            router_config = ConfigManager.get_router_config(config, router_name)
            if router_config:
                self.router_configs.append(router_config)
        
        # Connect to all routers
        devices = self.device_manager.connect_all(self.router_configs)
        
        return len(devices) > 0
    
    def get_all_versions(self):
        """Get version information for all connected routers"""
        print(f"\n{'='*80}")
        print("STEP 2: Device Information")
        print(f"{'='*80}")
        
        self.device_manager.get_all_versions()
    
    def configure_p2p_links(self, router_pairs=None):
        """
        Configure P2P links between router pairs.
        
        Args:
            router_pairs (list): List of tuples [(r0, r1), (r1, r2), ...]. 
                                If None, will prompt user for pairs.
        
        Returns:
            list: List of configuration results
        """
        print(f"\n{'='*80}")
        print("STEP 3: P2P Link Configuration")
        print(f"{'='*80}")
        
        if router_pairs is None:
            # Interactive mode
            print(f"\nAvailable routers: {', '.join(self.router_names)}")
            print("\nEnter router pairs to configure P2P links.")
            print("Format: router1,router2 (e.g., r0,r1)")
            print("Enter 'done' when finished.\n")
            
            router_pairs = []
            while True:
                pair_input = input("Enter router pair (or 'done'): ").strip()
                if pair_input.lower() == 'done':
                    break
                
                try:
                    r1, r2 = pair_input.split(',')
                    r1, r2 = r1.strip(), r2.strip()
                    
                    if r1 not in self.router_names or r2 not in self.router_names:
                        print(f"✗ Invalid router name(s). Available: {', '.join(self.router_names)}")
                        continue
                    
                    router_pairs.append((r1, r2))
                    print(f"✓ Added pair: {r1} <-> {r2}")
                except:
                    print("✗ Invalid format. Use: router1,router2")
        
        if not router_pairs:
            print("No router pairs specified")
            return []
        
        # Configure each pair
        results = []
        for r1, r2 in router_pairs:
            dev1 = self.device_manager.devices.get(r1)
            dev2 = self.device_manager.devices.get(r2)
            
            result = P2PLinkConfigurator.configure_p2p_link(
                yaml_config_file=self.yaml_config_file,
                router1_name=r1,
                router2_name=r2,
                dev1=dev1,
                dev2=dev2,
                ip_address=None,
                group_name=f'P2P_{r1}_{r2}'
            )
            
            results.append(result)
            
            if result["success"]:
                print(f"\n✓ {r1} <-> {r2} configured successfully")
            else:
                print(f"\n✗ {r1} <-> {r2} failed: {result.get('error')}")
        
        return results
    
    def run(self, router_pairs=None):
        """
        Execute complete automation workflow.
        
        Args:
            router_pairs (list, optional): Specific router pairs to configure
        """
        try:
            # Step 1: Discover and connect
            if not self.discover_and_connect():
                print("\n✗ No devices connected. Exiting.")
                return
            
            # Step 2: Get device versions
            self.get_all_versions()
            
            # Step 3: Configure P2P links
            results = self.configure_p2p_links(router_pairs)
            
            # Summary
            print(f"\n{'='*80}")
            print("AUTOMATION SUMMARY")
            print(f"{'='*80}")
            print(f"Total routers discovered: {len(self.router_names)}")
            print(f"Total routers connected: {len([d for d in self.device_manager.devices.values() if d])}")
            print(f"Total P2P links configured: {len([r for r in results if r.get('success')])}/{len(results)}")
            print(f"{'='*80}")
        
        except Exception as e:
            print(f"\n✗ An error occurred: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Always close connections
            self.device_manager.close_all()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python script.py <config_file.yaml> [router1,router2 ...]")
        print("\nExamples:")
        print("  python script.py routers.yaml                  # Interactive mode")
        print("  python script.py routers.yaml r0,r1 r1,r2     # Configure specific pairs")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    # Parse router pairs from command line
    router_pairs = None
    if len(sys.argv) > 2:
        router_pairs = []
        for pair_str in sys.argv[2:]:
            try:
                r1, r2 = pair_str.split(',')
                router_pairs.append((r1.strip(), r2.strip()))
            except:
                print(f"✗ Invalid pair format: {pair_str}")
                sys.exit(1)
    
    print(f"\n{'='*80}")
    print("JUNOS AUTOMATION ORCHESTRATOR")
    print(f"Configuration: {config_file}")
    print(f"{'='*80}")
    
    orchestrator = JunosAutomationOrchestrator(config_file)
    orchestrator.run(router_pairs)
