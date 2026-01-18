#!/usr/bin/env python3
"""
Junos PyEZ Library - Configuration Export with XML, JSON, and SET Formats
CORRECTED VERSION - Uses rpc.command() for operational mode CLI

The fix: Use rpc.command() to execute at ">" prompt level, not config mode
Commands execute as: show configuration | display xml (at operational level)
"""

import yaml, sys, json, os
from pathlib import Path
from typing import Dict, List, Any, Optional
from xml.dom import minidom
from xml.etree import ElementTree as ET
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.exception import ConnectError, ConfigLoadError, CommitError

try:
    import ansible_runner
    ANSIBLE_RUNNER_AVAILABLE = True
except ImportError:
    ANSIBLE_RUNNER_AVAILABLE = False

try:
    from yaml_flattener_with_access import yaml_to_flattened_database
    from flatjson2vars import load_flattened_json
    YAML_FLATTENER_AVAILABLE = True
except ImportError:
    YAML_FLATTENER_AVAILABLE = False


class JunosDeviceManager:
    """Manages connections to Junos devices"""
    
    def __init__(self, host, user, password, port=22):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.device = None
        self.is_connected = False

    def connect(self):
        try:
            print(f"Connecting to {self.host}...")
            self.device = Device(host=self.host, user=self.user, passwd=self.password, port=self.port)
            self.device.open()
            self.is_connected = True
            print(f"✓ Successfully connected to {self.host}")
        except ConnectError as err:
            print(f"✗ Cannot connect to device: {err}")
            raise

    def disconnect(self):
        if self.device and self.is_connected:
            self.device.close()
            self.is_connected = False
            print(f"Disconnected from {self.host}")

    def get_facts(self):
        if not self.is_connected:
            raise RuntimeError("Device not connected. Call connect() first.")
        facts = self.device.facts
        version = facts.get('version')
        model = facts.get('model')
        hostname = facts.get('hostname')
        serial = facts.get('serialnumber', 'N/A').lower()
        print(f"\nDevice Facts for {self.host}:")
        print(f" Hostname: {hostname}\n Model: {model}\n Junos Version: {version}\n Serial Number: {serial}")
        return {'version': version, 'model': model, 'hostname': hostname, 'serial': serial}

    def get_chassis_id(self):
        if not self.is_connected:
            raise RuntimeError("Device not connected. Call connect() first.")
        try:
            rpc_result = self.device.rpc.get_chassis_inventory()
            chassis = rpc_result.find('.//chassis')
            if chassis is not None:
                serial_number = chassis.findtext('serial-number')
                return serial_number.lower() if serial_number else None
        except Exception as e:
            print(f"Error retrieving chassis ID: {e}")
            return None

    def get_lldp_neighbors(self):
        if not self.is_connected:
            raise RuntimeError("Device not connected. Call connect() first.")
        try:
            lldp_info = self.device.rpc.get_lldp_neighbors_information()
            neighbors = []
            for neighbor in lldp_info.findall('.//lldp-neighbor-information'):
                neighbors.append({
                    'local_port': neighbor.findtext('lldp-local-port-id', 'Unknown'),
                    'local_parent': neighbor.findtext('lldp-local-parent-interface-name', '-'),
                    'remote_chassis_id': neighbor.findtext('lldp-remote-chassis-id', 'Unknown').lower(),
                    'remote_port': neighbor.findtext('lldp-remote-port-description', 'Unknown'),
                    'remote_system': neighbor.findtext('lldp-remote-system-name', 'Unknown')
                })
            return neighbors
        except Exception as e:
            print(f"Error retrieving LLDP neighbors: {e}")
            return []

    def get_configuration_xml(self, router_name: str) -> Optional[str]:
        """
        Retrieve complete device configuration in XML format
        Command: show configuration | display xml (at operational mode >)
        
        CORRECTED: Uses rpc.command() to execute at ">" prompt level
        """
        if not self.is_connected:
            print(f"[{router_name}] Device not connected, cannot retrieve configuration.")
            return None
        
        try:
            print(f"\n[{router_name}] Retrieving device configuration in XML format...")
            print(f"[{router_name}] Command: show configuration | display xml")
            
            # Execute at operational mode (>) using rpc.command()
            result = self.device.rpc.command(
                'show configuration | display xml |no-more',
                format='text'
            )
            
            # Extract output text
            if result is None:
                print(f"[{router_name}] ✗ No output returned")
                return None
            
            # Handle different return types
            if hasattr(result, 'text'):
                config_xml = result.text
            elif isinstance(result, str):
                config_xml = result
            else:
                config_xml = ET.tostring(result, encoding='unicode')
            
            # Verify we have actual content
            if not config_xml or config_xml.strip() == '':
                print(f"[{router_name}] ✗ Empty configuration returned")
                return None
            
            print(f"[{router_name}] ✓ Configuration XML retrieved ({len(config_xml)} bytes)")
            return config_xml
            
        except Exception as e:
            print(f"[{router_name}] Error retrieving configuration XML: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_configuration_json(self, router_name: str) -> Optional[str]:
        """
        Retrieve complete device configuration in JSON format
        Command: show configuration | display json (at operational mode >)
        
        CORRECTED: Uses rpc.command() to execute at ">" prompt level
        """
        if not self.is_connected:
            print(f"[{router_name}] Device not connected, cannot retrieve configuration.")
            return None
        
        try:
            print(f"[{router_name}] Retrieving device configuration in JSON format...")
            print(f"[{router_name}] Command: show configuration | display json")
            
            # Execute at operational mode (>) using rpc.command()
            result = self.device.rpc.command(
                'show configuration | display json | no-more',
                format='text'
            )
            
            # Extract output text
            if result is None:
                print(f"[{router_name}] ✗ No output returned")
                return None
            
            # Handle different return types
            if hasattr(result, 'text'):
                config_json = result.text
            elif isinstance(result, str):
                config_json = result
            else:
                config_json = ET.tostring(result, encoding='unicode')
            
            # Verify we have actual content
            if not config_json or config_json.strip() == '':
                print(f"[{router_name}] ✗ Empty configuration returned")
                return None
            
            print(f"[{router_name}] ✓ Configuration JSON retrieved ({len(config_json)} bytes)")
            return config_json
            
        except Exception as e:
            print(f"[{router_name}] Error retrieving configuration JSON: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_configuration_set(self, router_name: str) -> Optional[str]:
        """
        Retrieve complete device configuration in SET format with inheritance
        Command: show configuration | display inheritance | display set (at operational mode >)
        
        CORRECTED: Uses rpc.command() to execute at ">" prompt level
        """
        if not self.is_connected:
            print(f"[{router_name}] Device not connected, cannot retrieve configuration.")
            return None
        
        try:
            print(f"[{router_name}] Retrieving device configuration in SET format with inheritance...")
            print(f"[{router_name}] Command: show configuration | display inheritance | display set")
            
            # Execute at operational mode (>) using rpc.command()
            result = self.device.rpc.command(
                'show configuration | display inheritance | display set | no-more',
                format='text'
            )
            
            # Extract output text
            if result is None:
                print(f"[{router_name}] ✗ No output returned")
                return None
            
            # Handle different return types
            if hasattr(result, 'text'):
                config_set = result.text
            elif isinstance(result, str):
                config_set = result
            else:
                config_set = ET.tostring(result, encoding='unicode')
            
            # Verify we have actual content
            if not config_set or config_set.strip() == '':
                print(f"[{router_name}] ✗ Empty configuration returned")
                return None
            
            print(f"[{router_name}] ✓ Configuration SET retrieved ({len(config_set)} bytes)")
            return config_set
            
        except Exception as e:
            print(f"[{router_name}] Error retrieving configuration SET: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_configuration_files(self, router_name: str, output_dir: str = "router_configs") -> Dict[str, str]:
        """
        Retrieve device configuration and save as XML, JSON, and SET files
        """
        if not self.is_connected:
            print(f"[{router_name}] Device not connected, skipping configuration export.")
            return {}
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            print(f"\n{'='*70}")
            print(f"[{router_name}] Exporting Device Configuration")
            print(f"{'='*70}")
            
            # Get XML configuration
            config_xml = self.get_configuration_xml(router_name)
            if not config_xml:
                print(f"[{router_name}] ✗ Failed to retrieve XML configuration")
                return {}
            
            # Get JSON configuration
            config_json = self.get_configuration_json(router_name)
            if not config_json:
                print(f"[{router_name}] ✗ Failed to retrieve JSON configuration")
                return {}
            
            # Get SET configuration with inheritance
            config_set = self.get_configuration_set(router_name)
            if not config_set:
                print(f"[{router_name}] ✗ Failed to retrieve SET configuration")
                return {}
            
            # Create filenames
            xml_filename = f"{output_dir}/{router_name}.xml"
            json_filename = f"{output_dir}/{router_name}.json"
            set_filename = f"{output_dir}/{router_name}.set"
            
            # Save XML file
            print(f"[{router_name}] Saving XML configuration to: {xml_filename}")
            with open(xml_filename, 'w') as f:
                try:
                    dom = minidom.parseString(config_xml)
                    f.write(dom.toprettyxml())
                except:
                    f.write(config_xml)
            print(f"[{router_name}] ✓ XML file saved successfully")
            
            # Save JSON file
            print(f"[{router_name}] Saving JSON configuration to: {json_filename}")
            with open(json_filename, 'w') as f:
                f.write(config_json)
            print(f"[{router_name}] ✓ JSON file saved successfully")
            
            # Save SET file
            print(f"[{router_name}] Saving SET configuration to: {set_filename}")
            with open(set_filename, 'w') as f:
                f.write(config_set)
            print(f"[{router_name}] ✓ SET file saved successfully")
            
            print(f"{'='*70}\n")
            
            return {
                'xml_file': xml_filename,
                'json_file': json_filename,
                'set_file': set_filename,
                'router_name': router_name,
                'hostname': self.device.facts.get('hostname'),
                'status': 'success'
            }
        
        except Exception as e:
            print(f"[{router_name}] ERROR: Failed to save configuration files: {e}")
            import traceback
            traceback.print_exc()
            return {}


class ConfigManager:
    """Manages YAML configuration files"""
    
    def __init__(self, yaml_file):
        self.yaml_file = yaml_file
        self.config_data = None

    def read_config(self):
        try:
            print(f"Loading configuration from '{self.yaml_file}'...")
            with open(self.yaml_file, 'r') as f:
                self.config_data = yaml.safe_load(f)
            print("Configuration loaded successfully")
            return self.config_data
        except FileNotFoundError:
            print(f"Error: Configuration file '{self.yaml_file}' not found.")
            raise
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            raise

    def flatten_config(self):
        if not YAML_FLATTENER_AVAILABLE:
            print("⚠ Warning: YAML flattener not available. Skipping config flattening.")
            return self.config_data
        return self.config_data


class JunosAutomationOrchestrator:
    """Main orchestrator for Junos device automation"""
    
    def __init__(self, yaml_config_file):
        self.config_manager = ConfigManager(yaml_config_file)
        self.device_managers = {}

    def run(self):
        """Execute automation workflow"""
        print("\n" + "="*70)
        print("Junos Automation Orchestrator - Configuration Export")
        print("XML | JSON | SET (with inheritance)")
        print("="*70 + "\n")

        print("Step 1: Reading configuration...")
        config = self.config_manager.read_config()
        routers = config.get('routers', {})
        router_count = len(routers)
        router_names = list(routers.keys())

        print(f"\n{'='*70}")
        print(f"📊 Configuration Summary:")
        print(f" Total Routers Found: {router_count}")
        print(f" Router Names: {', '.join(router_names)}")
        print(f"{'='*70}\n")

        print("\n" + "="*70)
        print(f"Step 2: Connecting to {router_count} router(s)...")
        print("="*70 + "\n")

        connected_count = 0
        failed_count = 0

        for router_name, router_config in routers.items():
            host = router_config.get('ip')
            user = router_config.get('username')
            password = router_config.get('password')

            if not host or not user or not password:
                print(f"[{router_name}] ERROR: Missing connection credentials")
                failed_count += 1
                continue

            try:
                dev_mgr = JunosDeviceManager(host, user, password)
                dev_mgr.connect()
                self.device_managers[router_name] = dev_mgr
                connected_count += 1
            except Exception as e:
                print(f"[{router_name}] Failed to connect: {e}")
                failed_count += 1

        print(f"\n{'='*70}")
        print(f"Connection Summary:\n ✓ Connected: {connected_count}/{router_count}\n ✗ Failed: {failed_count}/{router_count}")
        print(f"{'='*70}\n")

        if connected_count == 0:
            print("ERROR: No devices connected. Exiting...")
            return

        print("\n" + "="*70)
        print(f"Step 3: Retrieving device facts from {connected_count} connected router(s)...")
        print("="*70 + "\n")

        facts_success = 0
        for router_name, dev_mgr in self.device_managers.items():
            try:
                dev_mgr.get_facts()
                facts_success += 1
            except Exception as e:
                print(f"[{router_name}] Failed to get facts: {e}")

        print(f"\nFacts Retrieved: {facts_success}/{connected_count} routers")

        # STEP 4: Export Router Configurations
        print("\n" + "="*70)
        print(f"Step 4: Exporting router configurations (XML, JSON & SET)...")
        print("="*70 + "\n")

        config_exports = {}
        export_success = 0
        export_failed = 0

        for router_name, dev_mgr in self.device_managers.items():
            try:
                result = dev_mgr.save_configuration_files(router_name)
                if result and result.get('status') == 'success':
                    config_exports[router_name] = result
                    export_success += 1
                else:
                    export_failed += 1
            except Exception as e:
                print(f"[{router_name}] Error exporting configuration: {e}")
                export_failed += 1

        print(f"\nConfiguration Export Summary:")
        print(f" ✓ Exported: {export_success}/{connected_count} routers")
        print(f" ✗ Failed: {export_failed}/{connected_count} routers")
        
        if config_exports:
            print(f"\nExported Configuration Files:")
            for router_name, export_info in config_exports.items():
                print(f"\n  [{router_name}]")
                print(f"   XML:  {export_info.get('xml_file')}")
                print(f"   JSON: {export_info.get('json_file')}")
                print(f"   SET:  {export_info.get('set_file')}")

        # Disconnect from all routers
        print("\n" + "="*70)
        print(f"Step 5: Disconnecting from {len(self.device_managers)} router(s)...")
        print("="*70 + "\n")

        for router_name, dev_mgr in self.device_managers.items():
            try:
                dev_mgr.disconnect()
            except Exception as e:
                print(f"[{router_name}] Error disconnecting: {e}")

        print("\n" + "="*70)
        print("🏁 Junos Automation Orchestrator - Completed")
        print("="*70)
        print(f"Total Routers Processed: {router_count}")
        print(f" Connections: {connected_count} successful, {failed_count} failed")
        print(f" Facts Retrieved: {facts_success} successful")
        print(f" Configurations Exported: {export_success} successful, {export_failed} failed")
        print(f"\nConfiguration Files Location: ./router_configs/")
        print("="*70 + "\n")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python script.py <yaml_config_file>")
        print("\nExample:")
        print("  python script.py ultimate_multi_routers_FIXED.yaml")
        sys.exit(1)

    yaml_config_file = sys.argv[1]

    if not os.path.exists(yaml_config_file):
        print(f"Error: Configuration file '{yaml_config_file}' not found")
        sys.exit(1)

    try:
        orchestrator = JunosAutomationOrchestrator(yaml_config_file)
        orchestrator.run()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
