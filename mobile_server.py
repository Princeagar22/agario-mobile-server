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
    def build_v25_server_info(host="reseau.proxy.rlwy.net", port=33266, token="token123"):
        """Build server_info protobuf message (required fields 1, 2, 3, 4, 5)"""
        msg = bytearray()
        # Field 1: server_id / type (varint)
        msg += ProtobufMessage.encode_tag(1, 0) + ProtobufMessage.encode_varint(1)
        # Field 2: host (string)
        msg += ProtobufMessage.encode_tag(2, 2) + ProtobufMessage.encode_string(host)
        # Field 3: port (varint)
        msg += ProtobufMessage.encode_tag(3, 0) + ProtobufMessage.encode_varint(port)
        # Field 4: token / country (string)
        msg += ProtobufMessage.encode_tag(4, 2) + ProtobufMessage.encode_string(token)
        # Field 5: status / ssl / type (varint - REQUIRED for 0x1f mask check at 0xcb7218!)
        msg += ProtobufMessage.encode_tag(5, 0) + ProtobufMessage.encode_varint(1)
        return bytes(msg)

    @staticmethod
    def build_v25_connect_response(host="reseau.proxy.rlwy.net", port=9000, token="token123"):
        """Build Agar.io v2.28+ connect_response (Type 33, containing server_info)"""
        si = ProtobufMessage.build_v25_server_info(host=host, port=port, token=token)
        msg = bytearray()
        msg += ProtobufMessage.encode_tag(1, 2) + ProtobufMessage.encode_varint(len(si)) + si
        return bytes(msg)

    @staticmethod
    def build_v25_device_token_update(token="token_ok"):
        """Build Agar.io v2.28+ device_token_update (Type 101, containing required string token)"""
        msg = bytearray()
        msg += ProtobufMessage.encode_tag(1, 2) + ProtobufMessage.encode_string(token)
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
    def encode_tag(field_num, wire_type):
        """Encode a protobuf tag"""
        return ProtobufMessage.encode_varint((field_num << 3) | wire_type)

    @staticmethod
    def parse_fields(data):
        """Parse raw protobuf wire bytes into a dict of field_number -> value"""
        fields = {}
        i = 0
        while i < len(data):
            tag = 0; shift = 0
            while True:
                if i >= len(data): break
                b = data[i]; i += 1
                tag |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            f_num = tag >> 3
            w_type = tag & 0x7
            if w_type == 0:
                val = 0; shift = 0
                while True:
                    if i >= len(data): break
                    b = data[i]; i += 1
                    val |= (b & 0x7f) << shift
                    if not (b & 0x80): break
                    shift += 7
                fields[f_num] = val
            elif w_type == 2:
                l = 0; shift = 0
                while True:
                    if i >= len(data): break
                    b = data[i]; i += 1
                    l |= (b & 0x7f) << shift
                    if not (b & 0x80): break
                    shift += 7
                fields[f_num] = data[i:i+l]
                i += l
            elif w_type == 5:
                i += 4
            elif w_type == 1:
                i += 8
            else:
                break
        return fields

    @staticmethod
    def build_v25_ping(channel=2):
        """Build Agar.io v2.28+ server ping envelope (req_type_enum 90)"""
        ping_submsg = ProtobufMessage.encode_tag(2, 0) + ProtobufMessage.encode_varint(0)
        req = bytearray()
        req += ProtobufMessage.encode_tag(87, 2) + ProtobufMessage.encode_varint(len(ping_submsg)) + ping_submsg
        req += ProtobufMessage.encode_tag(76, 0) + ProtobufMessage.encode_varint(90)
        env = bytearray()
        env += ProtobufMessage.encode_tag(2, 2) + ProtobufMessage.encode_varint(len(req)) + req
        env += ProtobufMessage.encode_tag(4, 0) + ProtobufMessage.encode_varint(channel)
        return struct.pack('>I', len(env)) + env

    @staticmethod
    def build_v25_user_info(account_id=12345, name="Guest"):
        """Build user_info protobuf message (Field 11 in login_response)"""
        msg = bytearray()
        # Field 1: account_id (varint)
        msg += ProtobufMessage.encode_tag(1, 0) + ProtobufMessage.encode_varint(account_id)
        # Field 2: name (string)
        msg += ProtobufMessage.encode_tag(2, 2) + ProtobufMessage.encode_string(name)
        # Field 3: level (varint)
        msg += ProtobufMessage.encode_tag(3, 0) + ProtobufMessage.encode_varint(1)
        # Field 4: xp (varint)
        msg += ProtobufMessage.encode_tag(4, 0) + ProtobufMessage.encode_varint(0)
        # Field 5: next_level_xp (varint)
        msg += ProtobufMessage.encode_tag(5, 0) + ProtobufMessage.encode_varint(100)
        # Field 6: country (string)
        msg += ProtobufMessage.encode_tag(6, 2) + ProtobufMessage.encode_string("US")
        return bytes(msg)

    @staticmethod
    def build_v25_user_stats():
        """Build user_stats protobuf message (Field 12 in login_response)"""
        msg = bytearray()
        # Field 1: games_played (varint)
        msg += ProtobufMessage.encode_tag(1, 0) + ProtobufMessage.encode_varint(0)
        # Field 2: highest_mass (varint)
        msg += ProtobufMessage.encode_tag(2, 0) + ProtobufMessage.encode_varint(0)
        # Field 3: total_mass (varint)
        msg += ProtobufMessage.encode_tag(3, 0) + ProtobufMessage.encode_varint(0)
        # Field 4: cells_eaten (varint)
        msg += ProtobufMessage.encode_tag(4, 0) + ProtobufMessage.encode_varint(0)
        return bytes(msg)

    @staticmethod
    def build_v25_login_response(account_id=12345, name="Guest", host="reseau.proxy.rlwy.net", port=33266, token="token123"):
        """Build Agar.io v2.28+ login_response (Type 118, Field 8 in req)
        Contains:
          - Field 1: status = 1 (SUCCESS) [REQUIRED by login_response::MergePartialFromCodedStream at 0x16b7838]
        """
        msg = bytearray()
        # Field 1: status = 1 (SUCCESS) - REQUIRED
        msg += ProtobufMessage.encode_tag(1, 0) + ProtobufMessage.encode_varint(1)
        return bytes(msg)


    @staticmethod
    def build_envelope_response(submsg_field, submsg_payload, channel=2):
        """Build an Agar.io v2.28+ Envelope containing a req message"""
        # Map req_type_enum to the exact field number in agario.proto.req:
        # Type 107 (pong) -> Field 1 (sets bit 0, inlined in req::IsInitialized at 0xcc5734)
        # Type 33 (connect_response) -> Field 10 (sets bit 9, checked in req::IsInitialized at 0xcc6050)
        # Type 118 (login_response) -> Field 8 (sets bit 7, verified in ByteSizeLong at 0xc78c68)
        type_to_req_field = {
            107: 1,   # pong
            33: 10,   # connect_response
            118: 8,   # login_response
            101: 45,  # device_token_update
            50: 54,   # configuration_change
            114: 56,  # game_enter_response
        }
        req_field = type_to_req_field.get(submsg_field, submsg_field)
        
        req = bytearray()
        req += ProtobufMessage.encode_tag(req_field, 2) + ProtobufMessage.encode_varint(len(submsg_payload)) + submsg_payload
        # Field 76: req_type_enum discriminator (REQUIRED by req::IsInitialized at 0xcc5714!)
        req += ProtobufMessage.encode_tag(76, 0) + ProtobufMessage.encode_varint(submsg_field)
        
        env = bytearray()
        env += ProtobufMessage.encode_tag(2, 2) + ProtobufMessage.encode_varint(len(req)) + req
        env += ProtobufMessage.encode_tag(4, 0) + ProtobufMessage.encode_varint(channel)
        
        return struct.pack('>I', len(env)) + env


    @staticmethod
    def encode_message(msg_type, payload, use_32bit=False):
        """Encode a message with size header (16-bit or 32-bit big-endian)"""
        size = len(payload) + 1  # +1 for type byte
        if use_32bit:
            header = struct.pack('>I', size)
        else:
            header = struct.pack('>H', size)
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
        self.running = True
        self.use_32bit = None
        self.keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
        self.keepalive_thread.start()
        logger.info(f"[{self.addr}] New connection accepted")
    
    def _keepalive_loop(self):
        """Send periodic pings for v2.28+ connections to keep session active"""
        while self.running:
            time.sleep(5)
            if not self.running:
                break
            if self.connected and self.use_32bit:
                try:
                    ping_packet = ProtobufMessage.build_v25_ping(channel=2)
                    self.sock.sendall(ping_packet)
                    logger.debug(f"[{self.addr}] [V25] Sent periodic ping")
                except:
                    break

    
    def send_message(self, msg_type, payload):
        """Send a protobuf message"""
        try:
            use_32 = self.use_32bit if self.use_32bit is not None else False
            msg = ProtobufMessage.encode_message(msg_type, payload, use_32bit=use_32)
            self.sock.sendall(msg)
            logger.info(f"[{self.addr}] Sent message type {msg_type} ({len(payload)} bytes payload, 32bit={use_32})")
        except Exception as e:
            logger.error(f"[{self.addr}] Error sending message: {e}")
            self.close()
    
    def recv_message(self):
        """Receive a protobuf message (auto-detecting 16-bit vs 32-bit length header)"""
        try:
            if self.use_32bit is None:
                first_2 = self.sock.recv(2)
                if len(first_2) < 2:
                    return None, None
                if first_2 == b'\x00\x00':
                    # 32-bit header (Agar.io v2.28+)
                    next_2 = self.sock.recv(2)
                    if len(next_2) < 2:
                        return None, None
                    self.use_32bit = True
                    size = struct.unpack('>I', first_2 + next_2)[0]
                    logger.info(f"[{self.addr}] Detected 32-bit packet header format (v2.28+), size={size}")
                else:
                    self.use_32bit = False
                    size = struct.unpack('>H', first_2)[0]
                    logger.info(f"[{self.addr}] Detected 16-bit packet header format (v2.0), size={size}")
            else:
                if self.use_32bit:
                    size_header = self.sock.recv(4)
                    if len(size_header) < 4:
                        return None, None
                    size = struct.unpack('>I', size_header)[0]
                else:
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
            
            if not msg_data:
                return None, None
            
            msg_type = msg_data[0]
            payload = bytes(msg_data[1:])
            logger.info(f"[{self.addr}] Received message type {msg_type} ({len(payload)} bytes payload): hex={payload[:32].hex()}")
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
                
                if msg_type == 18:
                    # Agar.io v2.28+ Protobuf Envelope
                    full_env = bytes([msg_type]) + payload
                    self.handle_v25_envelope(full_env)
                    continue

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
                    logger.warning(f"[{self.addr}] Unknown message type: {msg_type}, hex: {payload.hex()}")
        
        except Exception as e:
            logger.error(f"[{self.addr}] Exception in handle: {e}")
        finally:
            self.close()
    
    def handle_v25_envelope(self, envelope_bytes):
        """Handle Agar.io v2.28+ protobuf envelope"""
        try:
            env = ProtobufMessage.parse_fields(envelope_bytes)
            req_bytes = env.get(2)
            channel = env.get(4, 2)
            if not req_bytes:
                return
            
            req = ProtobufMessage.parse_fields(req_bytes)
            req_id = req.get(76)
            logger.info(f"[{self.addr}] [V25 REQ] req_id={req_id}, fields={list(req.keys())}")
            
            # Field 20: connect_request
            if 20 in req:
                logger.info(f"[{self.addr}] [V25] Handshake CONNECT_REQUEST received (req_id={req_id})")
                cr_payload = ProtobufMessage.build_v25_connect_response(
                    host="reseau.proxy.rlwy.net", port=33266, token=self.session_token
                )
                resp = ProtobufMessage.build_envelope_response(33, cr_payload, channel=channel)
                self.sock.sendall(resp)
                self.connected = True
                logger.info(f"[{self.addr}] [V25] Sent CONNECT_RESPONSE (Type 33)")
                
                # Send LOGIN_RESPONSE with full user_info and server_info
                login_payload = ProtobufMessage.build_v25_login_response(
                    account_id=self.player_id, name=self.player_name, host="reseau.proxy.rlwy.net", port=33266, token=self.session_token
                )
                resp_login = ProtobufMessage.build_envelope_response(118, login_payload, channel=channel)
                self.sock.sendall(resp_login)
                self.logged_in = True
                logger.info(f"[{self.addr}] [V25] Sent rich LOGIN_RESPONSE (Type 118)")
                
                # Send DEVICE_TOKEN_UPDATE
                dt_payload = ProtobufMessage.build_v25_device_token_update(token="token_" + str(self.player_id))
                resp_dt = ProtobufMessage.build_envelope_response(101, dt_payload, channel=channel)
                self.sock.sendall(resp_dt)
                logger.info(f"[{self.addr}] [V25] Sent DEVICE_TOKEN_UPDATE (Type 101)")

                # Send Server PING (Type 90) to trigger client's onConnection handler!
                ping_packet = ProtobufMessage.build_v25_ping(channel=channel)
                self.sock.sendall(ping_packet)
                logger.info(f"[{self.addr}] [V25] Sent Server PING (Type 90) to activate connection!")
            
            # Field 1 or req_id 107: client replied with pong
            elif 1 in req or req_id == 107:
                logger.info(f"[{self.addr}] [V25] Client PONG (Type 107) received!")
                login_payload = ProtobufMessage.build_v25_login_response(
                    account_id=self.player_id, name=self.player_name, host="reseau.proxy.rlwy.net", port=33266, token=self.session_token
                )
                resp = ProtobufMessage.build_envelope_response(118, login_payload, channel=channel)
                self.sock.sendall(resp)
                self.logged_in = True
                logger.info(f"[{self.addr}] [V25] Sent rich LOGIN_RESPONSE on PONG (Type 118, Field 8)")
                
                dt_payload = ProtobufMessage.build_v25_device_token_update(token="token_" + str(self.player_id))
                resp_dt = ProtobufMessage.build_envelope_response(101, dt_payload, channel=channel)
                self.sock.sendall(resp_dt)
                logger.info(f"[{self.addr}] [V25] Sent DEVICE_TOKEN_UPDATE on PONG (Type 101)")
            
            # Field 87 or 90: ping -> reply with pong (Type 107)
            elif 87 in req or 90 in req or req_id == 90:
                logger.info(f"[{self.addr}] [V25] Field 87/90 ping received (req_id={req_id})")
                pong_payload = ProtobufMessage.encode_tag(1, 2) + ProtobufMessage.encode_string("pong")
                resp = ProtobufMessage.build_envelope_response(107, pong_payload, channel=channel)
                self.sock.sendall(resp)
                logger.info(f"[{self.addr}] [V25] Sent PONG (Type 107)")
            
            # Login or game requests
            elif any(f in req for f in [3, 21, 23, 24, 26, 75]):
                logger.info(f"[{self.addr}] [V25] LOGIN_REQUEST received (req_id={req_id})")
                login_payload = ProtobufMessage.build_v25_login_response(
                    account_id=self.player_id, name=self.player_name, host="reseau.proxy.rlwy.net", port=33266, token=self.session_token
                )
                resp = ProtobufMessage.build_envelope_response(118, login_payload, channel=channel)
                self.sock.sendall(resp)
                self.logged_in = True
                logger.info(f"[{self.addr}] [V25] Sent rich LOGIN_RESPONSE (Type 118)")

            
            else:
                logger.info(f"[{self.addr}] [V25] Other request with fields {list(req.keys())}, req_id={req_id}")
                for k, v in req.items():
                    if isinstance(v, bytes):
                        logger.info(f"[{self.addr}] [V25] Field {k} len={len(v)}: hex={v[:32].hex()}")
                    else:
                        logger.info(f"[{self.addr}] [V25] Field {k}: val={v}")
                pong_payload = ProtobufMessage.encode_tag(1, 2) + ProtobufMessage.encode_string("pong")
                resp = ProtobufMessage.build_envelope_response(107, pong_payload, channel=channel)
                self.sock.sendall(resp)
        except Exception as e:
            logger.error(f"[{self.addr}] Error handling v25 envelope: {e}")
    
    def send_keepalive(self):
        """Send a keep-alive message"""
        try:
            use_32 = self.use_32bit if self.use_32bit is not None else False
            msg = ProtobufMessage.encode_message(99, b'', use_32bit=use_32)
            self.sock.sendall(msg)
            logger.info(f"[{self.addr}] Sent keep-alive")
        except:
            pass
    
    def close(self):
        """Close the connection"""
        self.running = False
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

