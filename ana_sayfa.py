import os
import sys
import json
import uuid
import hashlib
import datetime
import socket
import struct
import subprocess
import webbrowser
import shutil
import platform
from tkinter import *
from tkinter import messagebox, ttk, filedialog

def run_child(binary_base_name, files):
    import platform, subprocess, os
    suffix = '.exe' if platform.system() == 'Windows' else ''
    child_name = binary_base_name + suffix
    child_path = get_resource_path(child_name)
    if not os.path.exists(child_path):
        messagebox.showerror("Bulunamadı", f"Uygulama bulunamadı:\n{child_path}")
        return
    try:
        subprocess.Popen([child_path] + list(files), shell=False)
    except Exception as e:
        messagebox.showerror("Hata", f"Uygulama başlatılamadı:\n{e}")


# Platforma özgü importlar
if platform.system() == 'Windows':
    try:
        import win32print
        import win32api
    except ImportError:
        messagebox.showerror("Hata", "Win32 modülleri yüklü değil. Lütfen pywin32 yükleyin.")
        sys.exit(1)
elif platform.system() == 'Linux':
    try:
        import cups
    except ImportError:
        messagebox.showwarning("Uyarı", "CUPS yüklü değil. Linux'ta yazdırma özelliği çalışmayabilir.")

def get_resource_path(relative_path):
    """Kaynak dosyaları için çapraz platform uyumlu yol oluşturur"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class LisansYoneticisi:
    def __init__(self):
        self.system = platform.system()
        self._init_paths()
        self.DENEME_SURESI = 5
        self.NTP_SUNUCU = "time.google.com"
        self.mac = self._get_mac()
        self.lisans_durumu = self._check_license()

    def _init_paths(self):
        """Platforma göre dosya yollarını ayarlar"""
        if self.system == 'Windows':
            appdata = os.getenv("APPDATA")
            self.DOSYA = os.path.join(appdata, "FotoğrafBaski", "lisans.json")
            os.makedirs(os.path.dirname(self.DOSYA), exist_ok=True)
        elif self.system == 'Darwin':
            app_support = os.path.expanduser('~/Library/Application Support')
            self.DOSYA = os.path.join(app_support, "FotoğrafBaski", "lisans.json")
            os.makedirs(os.path.dirname(self.DOSYA), exist_ok=True)
        else:  # Linux/Unix
            local_share = os.getenv('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
            self.DOSYA = os.path.join(local_share, "FotoğrafBaski", "lisans.json")
            os.makedirs(os.path.dirname(self.DOSYA), exist_ok=True)

    def _get_mac(self):
        """Platforma göre MAC adresi alır"""
        try:
            if self.system == 'Linux':
                # Linux için MAC adresi alma
                import fcntl
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes('eth0'[:15], 'utf-8')))
                return ':'.join('%02x' % b for b in info[18:24])
            else:
                # Windows ve macOS için standart yöntem
                mac_int = uuid.getnode()
                mac_hex = hex(mac_int)[2:].zfill(12)
                return ":".join(mac_hex[i:i+2] for i in range(0, 12, 2))
        except Exception:
            return "00:00:00:00:00:00"

    def _get_ntp_time(self):
        """NTP sunucusundan zaman al"""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(2)
            data = b'\x1b' + 47 * b'\0'
            client.sendto(data, (self.NTP_SUNUCU, 123))
            data, _ = client.recvfrom(1024)
            t = struct.unpack('!12I', data)[10] - 2208988800
            return datetime.datetime.fromtimestamp(t)
        except Exception:
            return datetime.datetime.now()

    def _checksum(self, data):
        """Veri bütünlüğü için checksum oluştur"""
        data_copy = data.copy()
        data_copy.pop("checksum", None)
        json_str = json.dumps(data_copy, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _check_license(self):
        """Lisans durumunu kontrol et"""
        if not os.path.exists(self.DOSYA):
            start_date = datetime.datetime.now().isoformat()
            data = {
                "status": "trial",
                "start_date": start_date,
                "mac": self.mac,
                "key": "",
                "last_check": start_date
            }
            data["checksum"] = self._checksum(data)
            try:
                with open(self.DOSYA, "w") as f:
                    json.dump(data, f, indent=2)
                return {"status": "trial", "days_left": self.DENEME_SURESI}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        try:
            with open(self.DOSYA, "r") as f:
                data = json.load(f)

            if data.get("checksum") != self._checksum(data):
                return {"status": "invalid", "reason": "Lisans dosyası bozuk"}
            if data.get("mac") != self.mac:
                return {"status": "invalid", "reason": "MAC adresi uyuşmazlığı"}

            now = self._get_ntp_time()
            if data["status"] == "trial":
                start = datetime.datetime.fromisoformat(data["start_date"]).date()
                days_left = self.DENEME_SURESI - (now.date() - start).days
                return {"status": "trial", "days_left": max(0, days_left)}
            elif data["status"]
