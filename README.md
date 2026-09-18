# Agar.io Mobile v2.0.3 Custom Server

A custom Python game server implementing the `agario.proto` protobuf protocol for Agar.io Mobile v2.0.3.

---

## Features
- Handles client connection requests (`CONNECT_REQUEST`, `CONNECT_RESPONSE`).
- Player login and session token generation (`LOGIN_REQUEST`, `LOGIN_RESPONSE`).
- Game arena entry handling (`GAME_ENTER_REQUEST`, `GAME_ENTER_RESPONSE`).
- Periodic heartbeat / keep-alive messages.
- Thread-safe connection handling for multiple simultaneous players.
- Fully compatible with Railway deployment.

---

## Railway Deployment Guide

> **IMPORTANT: Agar.io mobile uses raw TCP sockets, NOT HTTP.**  
> On Railway, you **must enable TCP Proxy** for the client to connect.

### 1. Deploy on Railway
1. Go to [Railway.app](https://railway.app) and create a **New Project**.
2. Select **Deploy from GitHub repo** and choose `agario-mobile-server`.
3. Railway will automatically detect the `Dockerfile` and deploy the service.

### 2. Enable TCP Proxy (Crucial!)
1. Click on your deployed service in the Railway project canvas.
2. Navigate to **Settings** -> **Networking**.
3. Under the **Public Networking** section, click **Add TCP Proxy**.
4. Railway will provide a public TCP endpoint, for example:
   ```
   Domain: roundhouse.proxy.rlwy.net
   Port:   12345
   ```
5. Note this domain and port — you will configure your game client to connect to this address.

---

## Connecting the Game Client (APK Patching)

Use `patch_apk.py` to point your Agar.io v2.0.3 APK to your Railway server:

```bash
python patch_apk.py <path_to_apk> <railway_tcp_domain> <railway_tcp_port>
```

**Example:**
```bash
python patch_apk.py "agar.io_2.0.3.apk" roundhouse.proxy.rlwy.net 12345
```

The script will:
1. Decompile the APK using `apktool`.
2. Patch `libgame.so` with your new server endpoint and port.
3. Rebuild and sign the patched APK.
4. Output `<name>_patched.apk` ready to install on Android.

---

## Running Locally

To run the server locally on port 9000:

```bash
python mobile_server.py
```

Or specify a custom port:

```bash
PORT=8080 python mobile_server.py
```
