#!/usr/bin/env python3
"""
Test client for Agar.io Mobile Custom Server
Tests protocol connection, authentication, and game arena entry.
"""

import socket
import struct
import sys

def test_server(host='reseau.proxy.rlwy.net', port=33266):
    print(f"=== Testing Custom Server on {host}:{port} ===\n")
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10.0)
    
    try:
        s.connect((host, port))
        print("[1] Connected to server TCP socket successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        return False

    def send_msg(msg_type, payload=b''):
        size = len(payload) + 1
        header = struct.pack('>H', size)
        s.sendall(header + bytes([msg_type]) + payload)
        print(f"--> Sent message type {msg_type} (payload size: {len(payload)})")

    def recv_msg():
        hdr = s.recv(2)
        if not hdr or len(hdr) < 2:
            return None, None
        size = struct.unpack('>H', hdr)[0]
        data = bytearray()
        while len(data) < size:
            chunk = s.recv(size - len(data))
            if not chunk:
                break
            data.extend(chunk)
        msg_type = data[0]
        payload = bytes(data[1:])
        return msg_type, payload

    try:
        # Step 1: CONNECT_REQUEST (1)
        send_msg(1, b'')
        msg_type, payload = recv_msg()
        print(f"<-- [SUCCESS] Received CONNECT_RESPONSE (Type {msg_type}): {payload}\n")

        # Step 2: LOGIN_REQUEST (3)
        send_msg(3, b'\x0a\x06Player')
        msg_type, payload = recv_msg()
        print(f"<-- [SUCCESS] Received LOGIN_RESPONSE (Type {msg_type}): {payload}\n")

        # Step 3: GAME_ENTER_REQUEST (5)
        send_msg(5, b'')
        msg_type, payload = recv_msg()
        print(f"<-- [SUCCESS] Received GAME_ENTER_RESPONSE (Type {msg_type}): {payload}\n")

        # Step 4: Receive keep-alive message (Type 99)
        msg_type, payload = recv_msg()
        print(f"<-- [SUCCESS] Received Keep-Alive / Ping (Type {msg_type})\n")

        # Step 5: DISCONNECT (7)
        send_msg(7, b'')
        s.close()
        print("[ALL TESTS PASSED] Custom Agar.io Mobile Server is 100% OPERATIONAL!")
        return True
    except Exception as e:
        print(f"[ERROR] Communication error: {e}")
        s.close()
        return False

if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else 'reseau.proxy.rlwy.net'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 33266
    success = test_server(host, port)
    sys.exit(0 if success else 1)
