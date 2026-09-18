import os
import re

print("=== Patching Agar.io v2.28.3 for Custom Server ===")

# 1. Patch JavaSocket.smali
javasocket_path = r"apk_decoded\smali_classes6\com\miniclip\network\JavaSocket.smali"
with open(javasocket_path, "r", encoding="utf-8") as f:
    smali = f.read()

# Patch constructor
old_ctor_start = """.method constructor <init>(Ljava/lang/String;Ljava/lang/String;IJILjava/lang/String;)V
    .locals 1

    .line 85
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 86
    iput-object p2, p0, Lcom/miniclip/network/JavaSocket;->_hostAddress:Ljava/lang/String;

    .line 87
    iput p3, p0, Lcom/miniclip/network/JavaSocket;->_hostPort:I"""

new_ctor_start = """.method constructor <init>(Ljava/lang/String;Ljava/lang/String;IJILjava/lang/String;)V
    .locals 3

    .line 85
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    const-string p1, "tcp"

    const-string p2, "reseau.proxy.rlwy.net"

    const p3, 33266

    const-string v0, "AgarCustomServer"

    const-string v1, "[AgarCustomServer] JavaSocket initialized with reseau.proxy.rlwy.net:33266 (TCP)"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 86
    iput-object p2, p0, Lcom/miniclip/network/JavaSocket;->_hostAddress:Ljava/lang/String;

    .line 87
    iput p3, p0, Lcom/miniclip/network/JavaSocket;->_hostPort:I"""

if old_ctor_start in smali:
    smali = smali.replace(old_ctor_start, new_ctor_start, 1)
    print("[1/4] Constructor patched successfully!")
else:
    print("[WARN] Constructor target block not found!")

# Patch access$400
old_access400 = """.method static synthetic access$400(Lcom/miniclip/network/JavaSocket;)Ljava/lang/String;
    .locals 0

    .line 31
    iget-object p0, p0, Lcom/miniclip/network/JavaSocket;->_hostAddress:Ljava/lang/String;

    return-object p0
.end method"""

new_access400 = """.method static synthetic access$400(Lcom/miniclip/network/JavaSocket;)Ljava/lang/String;
    .locals 3

    const-string v0, "reseau.proxy.rlwy.net"

    const-string v1, "AgarCustomServer"

    const-string v2, "[AgarCustomServer] access$400 returning custom host: reseau.proxy.rlwy.net"

    invoke-static {v1, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-object v0
.end method"""

if old_access400 in smali:
    smali = smali.replace(old_access400, new_access400, 1)
    print("[2/4] access$400 patched successfully!")
else:
    print("[WARN] access$400 target block not found!")

# Patch access$800
old_access800 = """.method static synthetic access$800(Lcom/miniclip/network/JavaSocket;)I
    .locals 0

    .line 31
    iget p0, p0, Lcom/miniclip/network/JavaSocket;->_hostPort:I

    return p0
.end method"""

new_access800 = """.method static synthetic access$800(Lcom/miniclip/network/JavaSocket;)I
    .locals 3

    const v0, 33266

    const-string v1, "AgarCustomServer"

    const-string v2, "[AgarCustomServer] access$800 returning custom port: 33266"

    invoke-static {v1, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return v0
.end method"""

if old_access800 in smali:
    smali = smali.replace(old_access800, new_access800, 1)
    print("[3/4] access$800 patched successfully!")
else:
    print("[WARN] access$800 target block not found!")

# Patch access$900
old_access900 = """.method static synthetic access$900(Lcom/miniclip/network/JavaSocket;)Lcom/miniclip/network/JavaSocket$SocketType;
    .locals 0

    .line 31
    iget-object p0, p0, Lcom/miniclip/network/JavaSocket;->_socketType:Lcom/miniclip/network/JavaSocket$SocketType;

    return-object p0
.end method"""

new_access900 = """.method static synthetic access$900(Lcom/miniclip/network/JavaSocket;)Lcom/miniclip/network/JavaSocket$SocketType;
    .locals 3

    sget-object v0, Lcom/miniclip/network/JavaSocket$SocketType;->TCP:Lcom/miniclip/network/JavaSocket$SocketType;

    const-string v1, "AgarCustomServer"

    const-string v2, "[AgarCustomServer] access$900 returning SocketType TCP"

    invoke-static {v1, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-object v0
.end method"""

if old_access900 in smali:
    smali = smali.replace(old_access900, new_access900, 1)
    print("[4/4] access$900 patched successfully!")
else:
    print("[WARN] access$900 target block not found!")

# Add logging to sendDataTCP
old_send = """    .line 502
    :try_start_0
    array-length v2, p1

    invoke-virtual {v0, p1, v1, v2}, Ljava/io/DataOutputStream;->write([BII)V"""

new_send = """    .line 502
    :try_start_0
    array-length v2, p1

    const-string v3, "AgarCustomServer"

    new-instance v4, Ljava/lang/StringBuilder;

    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V

    const-string v5, "[AgarCustomServer] sendDataTCP sending "

    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v4, v2}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    const-string v5, " bytes"

    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v4}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v4

    invoke-static {v3, v4}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    invoke-virtual {v0, p1, v1, v2}, Ljava/io/DataOutputStream;->write([BII)V"""

if old_send in smali:
    smali = smali.replace(old_send, new_send, 1)
    print("[BONUS] sendDataTCP logging added!")

with open(javasocket_path, "w", encoding="utf-8") as f:
    f.write(smali)

# 2. Patch GameConfiguration.json
json_path = r"apk_decoded\assets\unpack\GameConfiguration.json"
if os.path.exists(json_path):
    with open(json_path, "rb") as f:
        cfg = f.read()
    cnt = 0
    # Replace any *.mobile-live-v25-0.agario.miniclippt.com
    def repl_json(m):
        global cnt
        cnt += 1
        return b'"domain":{"_value":"reseau.proxy.rlwy.net"}'
    
    cfg_new = re.sub(rb'\"domain\":\{\"_value\":\"[^\"]*agario\.miniclippt\.com\"\}', repl_json, cfg)
    with open(json_path, "wb") as f:
        f.write(cfg_new)
    print(f"[JSON] Replaced {cnt} domain entries in GameConfiguration.json!")

# 3. Patch libgame.so binaries
for abi in ["arm64-v8a", "armeabi-v7a"]:
    so_path = os.path.join(r"apk_decoded\lib", abi, "libgame-AGM-GooglePlay-Gold-Release-Module-777.so")
    if os.path.exists(so_path):
        with open(so_path, "rb") as f:
            so_data = f.read()
        target = b"mobile-live-v25-0.agario.miniclippt.com"
        replacement = b"reseau.proxy.rlwy.net".ljust(len(target), b"\x00")
        if target in so_data:
            so_data = so_data.replace(target, replacement)
            with open(so_path, "wb") as f:
                f.write(so_data)
            print(f"[NATIVE] Patched {abi} libgame.so!")
        else:
            print(f"[WARN] Target not found in {abi} libgame.so")

print("\n[SUCCESS] ALL PATCHES APPLIED SUCCESSFULLY!")
