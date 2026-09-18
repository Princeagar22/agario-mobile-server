#!/usr/bin/env python3
"""
Patch Agar.io v2.0.3 APK to connect to custom server endpoint (e.g. Railway TCP Proxy)
Directly patches libgame.so and re-signs APK without requiring apktool.
"""

import os
import sys
import zipfile
import subprocess

def patch_apk(apk_path, new_host='reseau.proxy.rlwy.net', new_port=33266, output_apk=None):
    if not os.path.exists(apk_path):
        print(f"[ERROR] APK not found: {apk_path}")
        return False

    work_dir = os.path.dirname(os.path.abspath(apk_path))
    if not output_apk:
        base_name = os.path.basename(apk_path).replace('.apk', '')
        output_apk = os.path.join(work_dir, f"{base_name}_railway.apk")

    print(f"\n[1] Patching APK: {apk_path}")
    print(f"    Target Server: {new_host}:{new_port}")
    print(f"    Output File:   {output_apk}")

    old_host_slot_len = 40  # 39 char host + 1 null terminator
    new_host_bytes = new_host.encode('utf-8').ljust(old_host_slot_len, b'\x00')
    if len(new_host_bytes) > old_host_slot_len:
        print(f"[ERROR] New host '{new_host}' is too long (max 39 characters).")
        return False

    new_port_str = str(new_port).encode('utf-8')

    with zipfile.ZipFile(apk_path, 'r') as zin, zipfile.ZipFile(output_apk, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            # Skip old signature files
            if item.filename.startswith('META-INF/'):
                continue
            
            data = zin.read(item.filename)
            
            if 'libgame.so' in item.filename:
                print(f"    Patching native binary: {item.filename}...")
                # Search for serverHost key
                host_key = b'serverHost\x00'
                port_key = b'serverPort\x00'
                
                h_idx = data.find(host_key)
                p_idx = data.find(port_key)
                
                if h_idx != -1 and p_idx != -1:
                    # Replace 40-byte host slot
                    host_start = h_idx + len(host_key)
                    data = data[:host_start] + new_host_bytes + data[host_start + old_host_slot_len:]
                    
                    # Update port slot
                    p_idx_new = data.find(port_key)
                    port_start = p_idx_new + len(port_key)
                    # Port slot is 5 bytes (e.g. 9000\x00 or 33266)
                    port_slot_len = 5
                    data = data[:port_start] + new_port_str[:port_slot_len].ljust(port_slot_len, b'\x00') + data[port_start + port_slot_len:]
                    print(f"    [OK] Successfully replaced endpoint with {new_host}:{new_port}")
                else:
                    print(f"    [WARN] serverHost/serverPort keys not found in {item.filename}")
            
            zout.writestr(item, data)

    print(f"\n[2] Signing APK...")
    keystore_path = os.path.join(work_dir, 'debug.keystore')
    if not os.path.exists(keystore_path):
        print("    Creating debug keystore...")
        subprocess.run([
            'keytool', '-genkey', '-v', '-keystore', keystore_path,
            '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
            '-alias', 'debug', '-storepass', 'android', '-keypass', 'android',
            '-dname', 'CN=Debug,O=Debug,L=Debug,S=Debug,C=US'
        ], check=True, stdout=subprocess.DEVNULL)

    sign_res = subprocess.run([
        'jarsigner', '-verbose', '-sigalg', 'SHA1withRSA', '-digestalg', 'SHA1',
        '-keystore', keystore_path, '-storepass', 'android', '-keypass', 'android',
        output_apk, 'debug'
    ], capture_output=True, text=True)

    if sign_res.returncode != 0:
        print(f"    [WARN] jarsigner exit code {sign_res.returncode}")

    print(f"\n✓ Patched & Signed APK ready: {output_apk}")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        apk_default = "agar.io_2.0.3_androidapksbox_patched (1).apk"
        host_default = "reseau.proxy.rlwy.net"
        port_default = 33266
        print(f"Using defaults: {apk_default} -> {host_default}:{port_default}")
        patch_apk(apk_default, host_default, port_default)
    else:
        apk_path = sys.argv[1]
        host = sys.argv[2] if len(sys.argv) > 2 else "reseau.proxy.rlwy.net"
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 33266
        patch_apk(apk_path, host, port)
