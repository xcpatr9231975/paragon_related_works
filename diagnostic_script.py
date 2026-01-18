#!/usr/bin/env python3
"""
DIAGNOSTIC SCRIPT - Test each method individually to see what works
Run this to identify which approach works with YOUR specific devices
"""

from jnpr.junos import Device
import sys

def test_device_connection(host, user, password):
    """Test connection and all possible methods"""
    
    print(f"\n{'='*70}")
    print(f"Testing device: {host}")
    print(f"{'='*70}\n")
    
    try:
        # Connect
        print("1. Connecting...")
        device = Device(host=host, user=user, passwd=password)
        device.open()
        print("   ✓ Connected\n")
        
        # Test 1: Get facts
        print("2. Getting facts...")
        facts = device.facts
        print(f"   Hostname: {facts.get('hostname')}")
        print(f"   Model: {facts.get('model')}")
        print(f"   Version: {facts.get('version')}\n")
        
        # Test 2: Simple CLI
        print("3. Testing simple CLI command (show version)...")
        try:
            result = device.cli('show version', format='text')
            print(f"   ✓ CLI works! Output length: {len(result)} bytes\n")
        except Exception as e:
            print(f"   ✗ CLI failed: {e}\n")
        
        # Test 3: RPC get_configuration with format='xml'
        print("4. Testing RPC get_configuration(format='xml')...")
        try:
            result = device.rpc.get_configuration(format='xml')
            if result is not None:
                from xml.etree import ElementTree as ET
                xml_str = ET.tostring(result, encoding='unicode')
                print(f"   ✓ RPC XML works! Output length: {len(xml_str)} bytes\n")
            else:
                print(f"   ✗ RPC returned None\n")
        except Exception as e:
            print(f"   ✗ RPC XML failed: {e}\n")
        
        # Test 4: RPC get_configuration with format='json'
        print("5. Testing RPC get_configuration(format='json')...")
        try:
            result = device.rpc.get_configuration(format='json')
            if result is not None:
                from xml.etree import ElementTree as ET
                json_str = ET.tostring(result, encoding='unicode')
                print(f"   ✓ RPC JSON works! Output length: {len(json_str)} bytes\n")
            else:
                print(f"   ✗ RPC returned None\n")
        except Exception as e:
            print(f"   ✗ RPC JSON failed: {e}\n")
        
        # Test 5: CLI show configuration | display xml
        print("6. Testing CLI 'show configuration | display xml'...")
        try:
            result = device.cli('show configuration | display xml', format='text')
            if result and result.strip():
                print(f"   ✓ CLI XML works! Output length: {len(result)} bytes\n")
            else:
                print(f"   ✗ CLI returned empty\n")
        except Exception as e:
            print(f"   ✗ CLI XML failed: {e}\n")
        
        # Test 6: CLI show configuration | display json
        print("7. Testing CLI 'show configuration | display json'...")
        try:
            result = device.cli('show configuration | display json', format='text')
            if result and result.strip():
                print(f"   ✓ CLI JSON works! Output length: {len(result)} bytes\n")
            else:
                print(f"   ✗ CLI returned empty\n")
        except Exception as e:
            print(f"   ✗ CLI JSON failed: {e}\n")
        
        # Test 7: CLI show configuration | display set
        print("8. Testing CLI 'show configuration | display set'...")
        try:
            result = device.cli('show configuration | display set', format='text')
            if result and result.strip():
                print(f"   ✓ CLI SET works! Output length: {len(result)} bytes\n")
            else:
                print(f"   ✗ CLI returned empty\n")
        except Exception as e:
            print(f"   ✗ CLI SET failed: {e}\n")
        
        # Disconnect
        device.close()
        print("✓ Disconnected\n")
        
    except Exception as e:
        print(f"✗ Fatal error: {e}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python diagnostic.py <host> <user> <password>")
        print("\nExample:")
        print("  python diagnostic.py 10.161.32.178 admin password123")
        sys.exit(1)
    
    host = sys.argv[1]
    user = sys.argv[2]
    password = sys.argv[3]
    
    test_device_connection(host, user, password)
    
    print(f"{'='*70}")
    print("RESULTS SUMMARY")
    print(f"{'='*70}")
    print("\nBased on the tests above, use the method that works best for your device.")
    print("Recommended order to try:")
    print("1. RPC get_configuration(format='xml') - most reliable")
    print("2. CLI 'show configuration | display xml' - alternative")
    print("3. RPC get_configuration(format='json') - for JSON format")
    print("4. CLI 'show configuration | display set' - for SET format")
    print()
