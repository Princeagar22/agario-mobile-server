#!/usr/bin/env python3
"""
Agar.io Mobile v2.0.3 Custom Server
Implements the agario.proto protocol for local testing
"""

import socket
import struct
import threading
import time
import random
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProtobufMessage:
    """Simple protobuf message encoder/decoder"""
    
    # Message type IDs (from agario.proto)
    CONNECT_REQUEST = 1
    CONNECT_RESPONSE = 2
    LOGIN_REQUEST = 3
    LOGIN_RESPONSE = 4
    GAME_ENTER_REQUEST = 5
    GAME_ENTER_RESPONSE = 6
    DISCONNECT = 7
    RECONNECT = 8
    
    @staticmethod
    def encode_varint(value):
        """Encode a variable-length integer"""
        result = bytearray()
        while value > 0x7f:
            result.append((value & 0x7f) | 0x80)
            value >>= 7
        result.append(value & 0x7f)
        return bytes(result)
    
    @staticmethod
    def decode_varint(data, offset=0):
        """Decode a variable-length integer"""
        result = 0
        shift = 0
        while True:
            byte = data[offset]
            result |= (byte & 0x7f) << shift
            offset += 1
            if not (byte & 0x80):
                break
            shift += 7
        return result, offset
    
    @staticmethod
    def encode_string(value):
        """Encode a string field"""
        encoded = value.encode('utf-8')
        return ProtobufMessage.encode_varint(len(encoded)) + encoded
    
    @staticmethod
    def decode_string(data, offset=0):
        """Decode a string field"""
        length, offset = ProtobufMessage.decode_varint(data, offset)
        value = data[offset:offset+length].decode('utf-8')
        return value, offset + length
    
    @staticmethod
    def build_connect_response(player_id=12345, session_token="token123"):
        """Build a CONNECT_RESPONSE message"""
        # message connect_response {
        #   required uint32 player_id = 1;
        #   required string session_token = 2;
        # }
        
        msg = bytearray()
        # Field 1: player_id (varint)
        msg += b'\x08'  # field 1, wire type 0 (varint)
        msg += ProtobufMessage.encode_varint(player_id)
        
        # Field 2: session_token (string)
        msg += b'\x12'  # field 2, wire type 2 (length-delimited)
        msg += ProtobufMessage.encode_string(session_token)
        
        return bytes(msg)
    
    @staticmethod
    def build_login_response(player_id=12345, player_name="Guest", status=0):
        """Build a LOGIN_RESPONSE message"""
        # message login_response {
        #   required uint32 status = 1;
        #   required uint32 player_id = 2;
        #   required string player_name = 3;
        # }
        
        msg = bytearray()
        # Field 1: status (varint) - 0 = success
        msg += b'\x08'
        msg += ProtobufMessage.encode_varint(status)
        
        # Field 2: player_id (varint)
        msg += b'\x10'
        msg += ProtobufMessage.encode_varint(player_id)
        
        # Field 3: player_name (string)
        msg += b'\x1a'
        msg += ProtobufMessage.encode_string(player_name)
        
        return bytes(msg)
    
    @staticmethod
    def build_game_enter_response(arena_id=1):
        """Build a GAME_ENTER_RESPONSE message"""
        msg = bytearray()
        # Field 1: arena_id (varint)
        msg += b'\x08'
        msg += ProtobufMessage.encode_varint(arena_id)
        return bytes(msg)
    
    @staticmethod
    def encode_message(msg_type, payload):
        """Encode a message with size header (16-bit big-endian)"""
        size = len(payload) + 1  # +1 for type byte
        header = struct.pack('>H', size)  # 16-bit big-endian
        return header + bytes([msg_type]) + payload


class ClientConnection:
    """Handles individual client connections"""
    
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.player_id = random.randint(10000, 99999)
        self.session_token = f"session_{self.player_id}_{int(time.time())}"
        self.player_name = "Guest"
        self.connected = False
        self.logged_in = False
        self.in_game = False
        logger.info(f"[{self.addr}] New connection accepted")
    
    def send_message(self, msg_type, payload):
        """Send a protobuf message"""
        try:
            msg = ProtobufMessage.encode_message(msg_type, payload)
            self.sock.sendall(msg)
            logger.info(f"[{self.addr}] Sent message type {msg_type} ({len(payload)} bytes payload)")
        except Exception as e:
            logger.error(f"[{self.addr}] Error sending message: {e}")
            self.close()
    
    def recv_message(self):
        """Receive a protobuf message"""
        try:
            # Read 16-bit size header
            size_header = self.sock.recv(2)
            if len(size_header) < 2:
                return None, None
            
            size = struct.unpack('>H', size_header)[0]
            
            # Read message type (1 byte) + payload
            msg_data = bytearray()
            remaining = size
            while remaining > 0:
                chunk = self.sock.recv(min(4096, remaining))
                if not chunk:
                    return None, None
                msg_data.extend(chunk)
                remaining -= len(chunk)
            
            msg_type = msg_data[0]
            payload = bytes(msg_data[1:])
            logger.info(f"[{self.addr}] Received message type {msg_type} ({len(payload)} bytes payload)")
            return msg_type, payload
        except socket.timeout:
            return None, None
        except Exception as e:
            logger.error(f"[{self.addr}] Error receiving message: {e}")
            return None, None
    
    def handle(self):
        """Handle client connection"""
        self.sock.settimeout(30.0)
        
        try:
            while True:
                msg_type, payload = self.recv_message()
                
                if msg_type is None:
                    logger.info(f"[{self.addr}] Client disconnected or timeout")
                    break
                
                if msg_type == ProtobufMessage.CONNECT_REQUEST:
                    logger.info(f"[{self.addr}] CONNECT_REQUEST received")
                    response = ProtobufMessage.build_connect_response(
                        self.player_id, self.session_token
                    )
                    self.send_message(ProtobufMessage.CONNECT_RESPONSE, response)
                    self.connected = True
                
                elif msg_type == ProtobufMessage.LOGIN_REQUEST:
                    logger.info(f"[{self.addr}] LOGIN_REQUEST received")
                    response = ProtobufMessage.build_login_response(
                        self.player_id, self.player_name, status=0
                    )
                    self.send_message(ProtobufMessage.LOGIN_RESPONSE, response)
                    self.logged_in = True
                    logger.info(f"[{self.addr}] Player {self.player_name} ({self.player_id}) logged in successfully")
                
                elif msg_type == ProtobufMessage.GAME_ENTER_REQUEST:
                    logger.info(f"[{self.addr}] GAME_ENTER_REQUEST received")
                    response = ProtobufMessage.build_game_enter_response(arena_id=1)
                    self.send_message(ProtobufMessage.GAME_ENTER_RESPONSE, response)
                    self.in_game = True
                    logger.info(f"[{self.addr}] Player entered game")
                    # Send periodic keep-alive/heartbeat messages
                    self.send_keepalive()
                
                elif msg_type == ProtobufMessage.DISCONNECT:
                    logger.info(f"[{self.addr}] DISCONNECT received")
                    break
                
                else:
                    logger.warning(f"[{self.addr}] Unknown message type: {msg_type}")
        
        except Exception as e:
            logger.error(f"[{self.addr}] Exception in handle: {e}")
        finally:
            self.close()
    
    def send_keepalive(self):
        """Send a keep-alive message (simple empty message)"""
        try:
            # Send a simple ping/keep-alive (could be any low message type)
            msg = ProtobufMessage.encode_message(99, b'')
            self.sock.sendall(msg)
            logger.info(f"[{self.addr}] Sent keep-alive")
        except:
            pass
    
    def close(self):
        """Close the connection"""
        try:
            self.sock.close()
        except:
            pass
        logger.info(f"[{self.addr}] Connection closed")


class MobileGameServer:
    """Main game server"""
    
    def __init__(self, host='0.0.0.0', port=9000):
        self.host = host
        self.port = port
        self.server_sock = None
        self.running = False
        self.clients = []
        self.client_lock = threading.Lock()
    
    def start(self):
        """Start the server"""
        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(100)
            self.running = True
            
            logger.info(f"[SERVER] Started on {self.host}:{self.port}")
            
            # Accept connections
            while self.running:
                try:
                    self.server_sock.settimeout(1.0)
                    sock, addr = self.server_sock.accept()
                    client = ClientConnection(sock, addr)
                    
                    with self.client_lock:
                        self.clients.append(client)
                    
                    # Handle client in separate thread
                    thread = threading.Thread(target=client.handle, daemon=True)
                    thread.start()
                
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"[SERVER] Error accepting connection: {e}")
        
        except Exception as e:
            logger.error(f"[SERVER] Error starting server: {e}")
        finally:
            if self.server_sock:
                self.server_sock.close()
            logger.info("[SERVER] Stopped")
    
    def stop(self):
        """Stop the server"""
        self.running = False


if __name__ == '__main__':
    import os
    import signal
    import sys

    port = int(os.environ.get('PORT', 9000))
    server = MobileGameServer('0.0.0.0', port)

    def handle_shutdown(signum, frame):
        logger.info(f"[SERVER] Received signal {signum}, shutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("[SERVER] Shutting down...")
        server.stop()

