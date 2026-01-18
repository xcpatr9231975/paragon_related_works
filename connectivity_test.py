#!/usr/bin/env python3
"""
CONNECTIVITY TEST - Check if you can reach the router
Helps diagnose connection issues before running full diagnostic
"""

import socket
import sys
from paramiko import SSHClient, AutoAddPolicy
import time

def test_connectivity(host, port=22):
    """Test basic network connectivity"""
    print(f"\n{'='*70}")
    print(f"CONNECTIVITY TEST: {host}:{port}")
    print(f"{'='*70}\n")
    
    # Test 1: Ping (socket connection)
    print(f"1. Testing basic TCP connection to {host}:{port}...")
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        print(f"   ✓ TCP connection successful\n")
        return True
    except socket.timeout:
        print(f"   ✗ Connection timeout - host is not responding\n")
        return False
    except socket.error as e:
        print(f"   ✗ Connection failed: {e}\n")
        return False

def test_ssh_banner(host, port=22):
    """Test SSH banner exchange"""
    print(f"2. Testing SSH banner exchange with {host}:{port}...")
    try:
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(host, port=port, username='test', password='test', 
                      look_for_keys=False, allow_agent=False, timeout=5)
        print(f"   ✓ SSH banner received (auth failed as expected)\n")
        client.close()
        return True
    except Exception as e:
        error_msg = str(e)
        if 'reset by peer' in error_msg or 'Connection refused' in error_msg:
            print(f"   ✗ SSH connection issue: {error_msg}\n")
            return False
        elif 'Authentication failed' in error_msg or 'username' in error_msg.lower():
            print(f"   ✓ SSH working (auth failed as expected): {e}\n")
            return True
        else:
            print(f"   ? Unclear result: {error_msg}\n")
            return False

def test_pyez_connection(host, user, password, port=22):
    """Test PyEZ connection"""
    print(f"3. Testing PyEZ connection with user '{user}'...")
    try:
        from jnpr.junos import Device
        device = Device(host=host, user=user, passwd=password, port=port, 
                       connect_timeout=10)
        device.open()
        print(f"   ✓ PyEZ connection successful!\n")
        
        # Get basic info
        try:
            facts = device.facts
            print(f"   Device Info:")
            print(f"   - Hostname: {facts.get('hostname')}")
            print(f"   - Model: {facts.get('model')}")
            print(f"   - Version: {facts.get('version')}\n")
        except:
            pass
        
        device.close()
        return True
    except Exception as e:
        print(f"   ✗ PyEZ connection failed: {e}\n")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python connectivity_test.py <host> <user> <password> [port]")
        print("\nExample:")
        print("  python connectivity_test.py 10.161.32.178 jnpr pass123")
        print("  python connectivity_test.py 10.161.32.178 jnpr pass123 830")
        sys.exit(1)
    
    host = sys.argv[1]
    user = sys.argv[2]
    password = sys.argv[3]
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 22
    
    # Run tests
    tcp_ok = test_connectivity(host, port)
    
    if tcp_ok:
        ssh_ok = test_ssh_banner(host, port)
        if ssh_ok:
            pyez_ok = test_pyez_connection(host, user, password, port)
    
    # Summary
    print(f"{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")
    print(f"Host: {host}:{port}")
    print(f"User: {user}")
    print("\nNext steps:")
    print("1. If TCP connection failed: Check firewall, IP address, and SSH port")
    print("2. If SSH failed: Check if SSH is enabled on that port")
    print("3. If PyEZ failed: Check username and password")
    print("4. If all pass: Run diagnostic_script.py to test config export methods")
    print()
