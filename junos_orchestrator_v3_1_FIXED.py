#!/usr/bin/env python3
"""
CORRECTED VERSION v3.1 - Uses RPC Instead of CLI Save
- Problem: PyEZ cli() doesn't support pipes/redirects (shell operators)
- Solution: Use dev.rpc.get_configuration(format='json/xml/set') instead
- This gets config directly to Python, avoiding shell save issues
"""

import yaml, sys, json, os, time, logging
from typing import Dict, Optional
from jnpr.junos import Device
from jnpr.junos.exception import ConnectError
from lxml import etree

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

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
            print(f"[CONNECT] Connecting to {self.host}:{self.port}...")
            logger.debug(f"Creating Device object with host={self.host}, user={self.user}, port={self.port}")
            
            self.device = Device(host=self.host, user=self.user, passwd=self.password, port=self.port)
            
            logger.debug("Device object created, calling device.open()...")
            self.device.open()
            
            self.is_connected = True
            print(f"✓ Connected\n")
            logger.debug("Connection successful!")
            
        except ConnectError as err:
            logger.error(f"Connection failed: {err}")
            print(f"✗ Cannot connect: {err}")
            raise

    def disconnect(self):
        if self.device and self.is_connected:
            logger.debug(f"Closing connection to {self.host}")
            self.device.close()
            self.is_connected = False
            print(f"Disconnected from {self.host}")

    def get_facts(self):
        if not self.is_connected:
            logger.warning("Device not connected, cannot get facts")
            return None
        
        logger.debug("Getting device facts...")
        facts = self.device.facts
        
        return {
            'version': facts.get('version'),
            'model': facts.get('model'),
            'hostname': facts.get('hostname'),
            'serial': facts.get('serialnumber', 'N/A').lower()
        }

    def get_config_via_rpc(self, router_name: str, format_type: str) -> Optional[str]:
        """
        Get configuration via RPC (NOT using shell save command)
        This is the CORRECT way to get config from PyEZ
        format_type: 'xml', 'json', or 'set'
        Returns: configuration as string
        """
        if not self.is_connected:
            logger.error(f"[{router_name}] Device not connected")
            print(f"[{router_name}] Not connected")
            return None
        
        print(f"[{router_name}] Getting {format_type.upper()} config via RPC...")
        logger.debug(f"[{router_name}] Calling rpc.get_configuration(format={format_type})")
        
        try:
            # Use RPC method - THIS IS THE KEY DIFFERENCE!
            # Instead of: dev.cli('show configuration | display json | save /path')
            # Use: dev.rpc.get_configuration(format='json')
            
            logger.debug(f"[{router_name}] Executing RPC call...")
            config_response = self.device.rpc.get_configuration(format=format_type)
            
            logger.debug(f"[{router_name}] RPC response type: {type(config_response)}")
            
            # Convert to string (lxml Element to text)
            if isinstance(config_response, str):
                config_text = config_response
                logger.debug(f"[{router_name}] Response is already string: {len(config_text)} chars")
            else:
                # lxml Element - convert to string
                config_text = etree.tostring(config_response, encoding='unicode', pretty_print=True)
                logger.debug(f"[{router_name}] Converted lxml to string: {len(config_text)} chars")
            
            if config_text and len(config_text.strip()) > 0:
                logger.debug(f"[{router_name}] ✓ Got {len(config_text)} bytes of config")
                print(f"[{router_name}] ✓ Got {len(config_text)} bytes")
                return config_text
            else:
                logger.error(f"[{router_name}] Empty config response")
                print(f"[{router_name}] ✗ Empty response")
                return None
            
        except Exception as e:
            logger.error(f"[{router_name}] ERROR getting config: {e}")
            import traceback
            logger.error(traceback.format_exc())
            print(f"[{router_name}] ERROR: {e}")
            return None

    def save_config_locally(self, router_name: str, format_type: str, config_text: str, output_dir: str = "router_configs") -> Optional[str]:
        """
        Save config text to local file
        Returns: local file path if successful
        """
        os.makedirs(output_dir, exist_ok=True)
        
        local_file = f"{output_dir}/{router_name}.{format_type}"
        
        try:
            print(f"[{router_name}] Saving to local file: {local_file}")
            logger.debug(f"[{router_name}] Opening file for writing...")
            
            with open(local_file, 'w') as f:
                bytes_written = f.write(config_text)
            
            logger.debug(f"[{router_name}] Wrote {bytes_written} bytes to {local_file}")
            
            # Verify file was created
            if os.path.exists(local_file):
                file_size = os.path.getsize(local_file)
                print(f"[{router_name}] ✓ File saved: {local_file} ({file_size} bytes)")
                logger.debug(f"[{router_name}] File verified, size: {file_size} bytes")
                return local_file
            else:
                logger.error(f"[{router_name}] File was not created")
                print(f"[{router_name}] ✗ File was not created")
                return None
                
        except Exception as e:
            logger.error(f"[{router_name}] ERROR saving file: {e}")
            print(f"[{router_name}] ERROR: {e}")
            return None

    def save_configuration_single_format(self, router_name: str, format_type: str, output_dir: str = "router_configs") -> Optional[str]:
        """
        Save a single configuration format:
        1. Get config via RPC (not shell save)
        2. Save to local file
        Returns: local filename if successful
        """
        if not self.is_connected:
            logger.error(f"[{router_name}] Device not connected")
            return None
        
        print(f"\n--- {format_type.upper()} Format ---")
        logger.debug(f"[{router_name}] Processing {format_type.upper()} format")
        
        try:
            # Step 1: Get config via RPC
            logger.debug(f"[{router_name}] Step 1: Getting config via RPC...")
            config_text = self.get_config_via_rpc(router_name, format_type)
            
            if not config_text:
                logger.error(f"[{router_name}] Failed to get {format_type} config")
                print(f"[{router_name}] ✗ Failed to get {format_type} config")
                return None
            
            # Step 2: Save locally
            logger.debug(f"[{router_name}] Step 2: Saving to local file...")
            local_file = self.save_config_locally(router_name, format_type, config_text, output_dir)
            
            if not local_file:
                logger.error(f"[{router_name}] Failed to save {format_type} locally")
                return None
            
            logger.debug(f"[{router_name}] ✓ {format_type.upper()} complete")
            print(f"[{router_name}] ✓ {format_type.upper()} done")
            
            return local_file
            
        except Exception as e:
            logger.error(f"[{router_name}] ERROR: {e}")
            import traceback
            logger.error(traceback.format_exc())
            print(f"[{router_name}] ERROR: {e}")
            return None

    def save_all_configurations(self, router_name: str, output_dir: str = "router_configs") -> Dict[str, str]:
        """
        Save XML, JSON, and SET configurations
        Uses RPC (NOT device shell save commands)
        """
        if not self.is_connected:
            logger.error(f"[{router_name}] Device not connected")
            print(f"[{router_name}] Not connected")
            return {}
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            print(f"\n{'='*70}")
            print(f"[{router_name}] Exporting Configurations (via RPC)")
            print(f"{'='*70}")
            logger.debug(f"[{router_name}] Starting configuration export")
            
            exports = {}
            
            # Process XML, JSON, SET
            for format_type in ['xml', 'json', 'set']:
                logger.debug(f"[{router_name}] Processing format: {format_type}")
                local_file = self.save_configuration_single_format(router_name, format_type, output_dir)
                if local_file:
                    exports[f'{format_type}_file'] = local_file
                    logger.debug(f"[{router_name}] Successfully saved {format_type}: {local_file}")
            
            if exports:
                exports['router_name'] = router_name
                exports['status'] = 'success'
                logger.debug(f"[{router_name}] Configuration export successful")
            else:
                logger.warning(f"[{router_name}] No configurations exported")
            
            print(f"{'='*70}\n")
            return exports
            
        except Exception as e:
            logger.error(f"[{router_name}] ERROR: {e}")
            import traceback
            logger.error(traceback.format_exc())
            print(f"[{router_name}] ERROR: {e}")
            return {}


class ConfigManager:
    """Manages YAML configuration files"""
    
    def __init__(self, yaml_file):
        self.yaml_file = yaml_file

    def read_config(self):
        logger.debug(f"Loading YAML config: {self.yaml_file}")
        print(f"Loading: '{self.yaml_file}'...")
        
        try:
            with open(self.yaml_file, 'r') as f:
                config_data = yaml.safe_load(f)
            print("✓ Configuration loaded\n")
            logger.debug(f"Config loaded successfully. Routers: {list(config_data.get('routers', {}).keys())}")
            return config_data
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise


class JunosAutomationOrchestrator:
    """Main orchestrator"""
    
    def __init__(self, yaml_config_file):
        self.config_manager = ConfigManager(yaml_config_file)
        self.device_managers = {}

    def run(self):
        """Execute workflow"""
        print("\n" + "="*70)
        print("Junos Automation Orchestrator - v3.1 (RPC-Based, No Shell Save)")
        print("="*70 + "\n")
        logger.debug("Starting Junos Automation Orchestrator v3.1")

        # Step 1: Read config
        logger.debug("Step 1: Reading configuration")
        config = self.config_manager.read_config()
        routers = config.get('routers', {})
        router_count = len(routers)
        router_names = list(routers.keys())
        print(f"Found {router_count} routers: {', '.join(router_names)}\n")
        logger.debug(f"Found {router_count} routers")

        # Step 2: Connect
        print("="*70)
        print(f"Connecting to {router_count} router(s)...")
        print("="*70 + "\n")
        logger.debug("Step 2: Connecting to routers")

        connected_count = 0
        for router_name, router_config in routers.items():
            host = router_config.get('ip')
            user = router_config.get('username')
            password = router_config.get('password')

            logger.debug(f"Attempting connection to {router_name}: {host}")
            
            if not host or not user or not password:
                logger.error(f"[{router_name}] Missing credentials")
                print(f"[{router_name}] ERROR: Missing credentials")
                continue

            try:
                dev_mgr = JunosDeviceManager(host, user, password)
                dev_mgr.connect()
                self.device_managers[router_name] = dev_mgr
                connected_count += 1
                logger.debug(f"[{router_name}] Connection successful")
            except Exception as e:
                logger.error(f"[{router_name}] Connection failed: {e}")
                print(f"[{router_name}] Failed: {e}\n")

        print(f"\nConnected: {connected_count}/{router_count} routers\n")
        logger.debug(f"Connected to {connected_count}/{router_count} routers")

        if connected_count == 0:
            logger.error("No devices connected, exiting")
            print("ERROR: No devices connected")
            return

        # Step 3: Get facts
        print("="*70)
        print("Getting device facts...")
        print("="*70 + "\n")
        logger.debug("Step 3: Getting device facts")

        for router_name, dev_mgr in self.device_managers.items():
            try:
                logger.debug(f"[{router_name}] Getting facts...")
                facts = dev_mgr.get_facts()
                if facts:
                    logger.debug(f"[{router_name}] Facts: {facts}")
                    print(f"[{router_name}] {facts.get('hostname')} ({facts.get('model')} v{facts.get('version')})\n")
            except Exception as e:
                logger.error(f"[{router_name}] Error getting facts: {e}")
                print(f"[{router_name}] Error: {e}")

        # Step 4: Export configurations
        print("="*70)
        print("Exporting configurations (via RPC)...")
        print("="*70 + "\n")
        logger.debug("Step 4: Exporting configurations")

        config_exports = {}
        export_success = 0

        for router_name, dev_mgr in self.device_managers.items():
            try:
                logger.debug(f"[{router_name}] Starting configuration export")
                result = dev_mgr.save_all_configurations(router_name)
                logger.debug(f"[{router_name}] Export result: {result}")
                
                if result and result.get('status') == 'success':
                    config_exports[router_name] = result
                    export_success += 1
                    logger.debug(f"[{router_name}] Export successful")
            except Exception as e:
                logger.error(f"[{router_name}] Export error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                print(f"[{router_name}] Error: {e}\n")

        print(f"Export Summary: {export_success}/{connected_count} successful\n")
        logger.debug(f"Export summary: {export_success}/{connected_count}")

        if config_exports:
            print("Exported Files (Local):")
            for router_name, export_info in config_exports.items():
                print(f"\n  [{router_name}]")
                logger.debug(f"[{router_name}] Export info: {export_info}")
                for key in ['xml_file', 'json_file', 'set_file']:
                    if key in export_info:
                        print(f"    {key.replace('_', ' ').title()}: {export_info.get(key)}")
            print()

        # Step 5: Disconnect
        print("="*70)
        print("Disconnecting...")
        print("="*70 + "\n")
        logger.debug("Step 5: Disconnecting")

        for router_name, dev_mgr in self.device_managers.items():
            try:
                logger.debug(f"[{router_name}] Disconnecting...")
                dev_mgr.disconnect()
            except Exception as e:
                logger.error(f"[{router_name}] Disconnect error: {e}")
                print(f"[{router_name}] Error: {e}")

        print("\n" + "="*70)
        print("✓ Completed")
        print("="*70)
        print(f"Summary: {router_count} routers, {connected_count} connected, {export_success} exported\n")
        logger.debug("Orchestrator completed successfully")


def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <yaml_config_file>")
        print("Example: python script.py ultimate_multi_routers_1127.yaml")
        logger.error("No config file provided")
        sys.exit(1)

    yaml_config_file = sys.argv[1]

    if not os.path.exists(yaml_config_file):
        print(f"Error: '{yaml_config_file}' not found")
        logger.error(f"Config file not found: {yaml_config_file}")
        sys.exit(1)

    try:
        logger.info(f"Starting with config file: {yaml_config_file}")
        orchestrator = JunosAutomationOrchestrator(yaml_config_file)
        orchestrator.run()
    except KeyboardInterrupt:
        print("\n\nCancelled")
        logger.warning("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
