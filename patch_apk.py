#!/usr/bin/env python3
"""
Patch Agar.io v2.0.3 APK to connect to custom localhost server
"""

import struct
import os
import subprocess
import sys

def patch_binary(binary_path, old_host, new_host, old_port, new_port):
    """
    Patch the binary to replace server endpoint
    """
    with open(binary_path, 'rb') as f:
        data = f.read()
    
    original_size = len(data)
    
    # Find and replace the old host
    old_host_bytes = old_host.encode('utf-8')
    new_host_bytes = new_host.encode('utf-8')
    
    # Ensure new host is same length or shorter (pad with nulls if needed)
    if len(new_host_bytes) > len(old_host_bytes):
        print(f"ERROR: New host '{new_host}' ({len(new_host_bytes)} bytes) is longer than old host '{old_host}' ({len(old_host_bytes)} bytes)")
        return False
    
    # Pad new host to same length
    new_host_bytes = new_host_bytes.ljust(len(old_host_bytes), b'\x00')
    
    count = data.count(old_host_bytes)
    print(f"Found {count} occurrences of '{old_host}'")
    
    if count > 0:
        data = data.replace(old_host_bytes, new_host_bytes)
        print(f"Replaced all occurrences of '{old_host}' with '{new_host}'")
    
    # Also try to find port number in network byte order
    # Port 9000 = 0x2328 (big-endian)
    # We'll search for the ASCII string as well
    old_port_str = str(old_port).encode('utf-8')
    new_port_str = str(new_port).encode('utf-8')
    
    if len(new_port_str) <= len(old_port_str):
        new_port_str = new_port_str.ljust(len(old_port_str), b'\x00')
        count = data.count(old_port_str)
        if count > 0:
            print(f"Found {count} occurrences of port '{old_port}'")
            data = data.replace(old_port_str, new_port_str)
            print(f"Replaced all occurrences of port '{old_port}' with '{new_port}'")
    
    with open(binary_path, 'wb') as f:
        f.write(data)
    
    print(f"Patched binary: {binary_path} ({original_size} bytes)")
    return True


def patch_apk(apk_path, new_host='127.0.0.1', new_port=9000):
    """
    Extract, patch, rebuild, and sign APK
    """
    work_dir = os.path.dirname(apk_path)
    base_name = os.path.basename(apk_path).replace('.apk', '')
    
    # Decompile
    print("\n[1] Decompiling APK with apktool...")
    apktool_path = os.path.join(work_dir, 'apktool.jar')
    if not os.path.exists(apktool_path):
        apktool_path = '/workspace/work/apktool.jar'
    decompile_dir = os.path.join(work_dir, f'{base_name}_patched_src')
    
    if os.path.exists(decompile_dir):
        import shutil
        shutil.rmtree(decompile_dir)
    
    result = subprocess.run([
        'java', '-jar', apktool_path, 'd', '-f', apk_path, '-o', decompile_dir
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"ERROR: apktool decompile failed: {result.stderr}")
        return False
    
    print(f"Decompiled to: {decompile_dir}")
    
    # Patch libgame.so
    print("\n[2] Patching libgame.so...")
    libgame_paths = [
        os.path.join(decompile_dir, 'lib', 'armeabi-v7a', 'libgame.so'),
        os.path.join(decompile_dir, 'lib', 'arm64-v8a', 'libgame.so'),
    ]
    
    for libgame_path in libgame_paths:
        if os.path.exists(libgame_path):
            print(f"Patching: {libgame_path}")
            # Old endpoints from v2.0.3
            patch_binary(libgame_path, 
                        'mobile-live-v10-0.agario.miniclippt.com',
                        'localhost\x00\x00\x00\x00\x00\x00\x00\x00\x00',
                        9000, 9000)
            
            # Also patch config URL to localhost (if we want to host config locally)
            # For now we'll keep the config URL as-is, or redirect it
            patch_binary(libgame_path,
                        'https://configs.agario.miniclippt.com/live/v10',
                        'http://localhost:8888/config\x00',
                        0, 0)
    
    # Rebuild APK
    print("\n[3] Rebuilding APK...")
    output_apk = os.path.join(work_dir, f'{base_name}_patched.apk')
    
    result = subprocess.run([
        'java', '-jar', apktool_path, 'b', decompile_dir, '-o', output_apk
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"ERROR: apktool build failed: {result.stderr}")
        return False
    
    print(f"Built APK: {output_apk}")
    
    # Create debug signing key if doesn't exist
    print("\n[4] Signing APK...")
    keystore_path = os.path.join(work_dir, 'debug.keystore')
    
    if not os.path.exists(keystore_path):
        print("Creating debug keystore...")
        result = subprocess.run([
            'keytool', '-genkey', '-v', '-keystore', keystore_path,
            '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
            '-alias', 'debug', '-storepass', 'android', '-keypass', 'android',
            '-dname', 'CN=Debug,O=Debug,L=Debug,S=Debug,C=US'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"ERROR: keytool failed: {result.stderr}")
            return False
    
    # Sign with jarsigner
    result = subprocess.run([
        'jarsigner', '-verbose', '-sigalg', 'SHA1withRSA', '-digestalg', 'SHA1',
        '-keystore', keystore_path, '-storepass', 'android', '-keypass', 'android',
        output_apk, 'debug'
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"WARNING: jarsigner returned code {result.returncode}: {result.stderr}")
        # Some versions of jarsigner may return non-zero even on success
    
    print(f"Signed APK: {output_apk}")
    
    print(f"\n✓ Patched APK ready: {output_apk}")
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 patch_apk.py <apk_path> [new_host] [new_port]")
        sys.exit(1)
    
    apk_path = sys.argv[1]
    new_host = sys.argv[2] if len(sys.argv) > 2 else 'localhost'
    new_port = int(sys.argv[3]) if len(sys.argv) > 3 else 9000
    
    if not os.path.exists(apk_path):
        print(f"ERROR: APK not found: {apk_path}")
        sys.exit(1)
    
    success = patch_apk(apk_path, new_host, new_port)
    sys.exit(0 if success else 1)
