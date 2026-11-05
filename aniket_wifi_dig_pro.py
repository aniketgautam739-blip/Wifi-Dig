#!/usr/bin/env python3
"""
Aniket's WiFi Dig 2  -  Router & Network Intelligence Suite
===========================================================
One window for an IT firm: everything about a router and the devices on its
network, what they cost to buy and to run, plus the electrical-engineering
and RF maths and vocabulary behind it.

  Router         live probe of the gateway (MAC, vendor, services, DHCP, HTTP banner,
                 RF/SNR/capacity maths) + your own spec sheet (EIRP, max PHY rate, cost)
  Devices & LAN  ping-sweep + ARP scan, vendor, OS guess, watts, price, running cost
  Wi-Fi Airspace nearby networks, channel occupancy graph, best-channel advice
  Cost & TCO     hardware + electricity + ISP, N-year total cost of ownership
  Calculators    16 EE/RF tools (dBm, FSPL, link budget, Shannon, VSWR, Ohm, PoE ...)
  Reference      Wi-Fi generations, channels, MCS, RSSI, cabling, PoE, security
  Glossary       120+ searchable technical terms
  Export         TXT / JSON / CSV report of everything on screen

Run:      python aniket_wifi_dig_pro.py
Optional: pip install psutil   (exact subnet mask + adapter MAC)
Best on Windows 10/11; Linux (NetworkManager) and macOS work with less detail.
Only scan networks and devices you own or are authorised to test.
"""

import concurrent.futures as cf
import csv
import ipaddress
import json
import math
import os
import platform
import queue
import re
import socket
import ssl
import subprocess
import threading
import time
import traceback
import uuid
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import psutil
except ImportError:
    psutil = None

APP_NAME = "Aniket's WiFi Dig"
VERSION = "2.0"
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
FONT = "Segoe UI" if IS_WIN else ("Helvetica Neue" if IS_MAC else "DejaVu Sans")

C = dict(bg="#0e1320", panel="#151c2e", card="#1b2440", line="#2a3556",
         accent="#4f8cff", good="#2ecc8f", warn="#f5a623", bad="#ff5c6c",
         text="#e9edf7", muted="#8d99b8")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".aniket_wifi_dig")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

DEFAULTS = {
    "tariff": 0.12, "currency": "$", "isp_fee": 0.0, "years": 3, "noise_dbm": -95,
    "router": {"model": "", "standard": "802.11ax (Wi-Fi 6)", "width": 80, "streams": 2,
               "tx_dbm": 20.0, "ant_gain": 3.0, "cable_loss": 0.0, "price": 0.0,
               "watts": 12.0, "hours": 24.0, "purchased": "", "notes": ""},
    "devices": {}, "oui_extra": {},
}


def load_settings():
    s = json.loads(json.dumps(DEFAULTS))
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(s.get(k), dict):
                s[k].update(v)
            else:
                s[k] = v
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        traceback.print_exc()


# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------
def run(cmd, timeout=20):
    try:
        kw = {"creationflags": 0x08000000} if IS_WIN else {}
        p = subprocess.run(cmd, capture_output=True, text=True, errors="ignore",
                           timeout=timeout, **kw)
        return p.stdout or p.stderr or ""
    except Exception:
        return ""


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def band_of(ch):
    return "-" if not ch else ("2.4 GHz" if ch <= 14 else "5/6 GHz")


def center_mhz(ch):
    if not ch:
        return None
    if ch <= 13:
        return 2407 + 5 * ch
    if ch == 14:
        return 2484
    return 5000 + 5 * ch


def rssi_quality(dbm):
    if dbm >= -50:
        return "Excellent"
    if dbm >= -60:
        return "Very good"
    if dbm >= -67:
        return "Good (VoIP/video OK)"
    if dbm >= -70:
        return "Fair"
    if dbm >= -80:
        return "Weak"
    return "Unusable"


# --------------------------------------------------------------------------
# Wi-Fi physics tables
# --------------------------------------------------------------------------
# std: (data subcarriers per width, bits/symbol, coding rate, symbol time us)
STD_PARAMS = {
    "802.11a/g (legacy OFDM)": ({20: 48}, 6, 0.75, 4.0),
    "802.11n (Wi-Fi 4)": ({20: 52, 40: 108}, 6, 5 / 6, 3.6),
    "802.11ac (Wi-Fi 5)": ({20: 52, 40: 108, 80: 234, 160: 468}, 8, 5 / 6, 3.6),
    "802.11ax (Wi-Fi 6)": ({20: 234, 40: 468, 80: 980, 160: 1960}, 10, 5 / 6, 13.6),
    "802.11be (Wi-Fi 7)": ({20: 234, 40: 468, 80: 980, 160: 1960, 320: 3920}, 12, 5 / 6, 13.6),
}
GEN_NAMES = {"802.11b": "Wi-Fi 1", "802.11a": "Wi-Fi 2", "802.11g": "Wi-Fi 3",
             "802.11n": "Wi-Fi 4", "802.11ac": "Wi-Fi 5", "802.11ax": "Wi-Fi 6/6E",
             "802.11be": "Wi-Fi 7"}

# (mcs, modulation, bits/symbol, coding num, coding text, min sensitivity dBm @20 MHz)
MCS = [(0, "BPSK", 1, 1 / 2, "1/2", -82), (1, "QPSK", 2, 1 / 2, "1/2", -79),
       (2, "QPSK", 2, 3 / 4, "3/4", -77), (3, "16-QAM", 4, 1 / 2, "1/2", -74),
       (4, "16-QAM", 4, 3 / 4, "3/4", -70), (5, "64-QAM", 6, 2 / 3, "2/3", -66),
       (6, "64-QAM", 6, 3 / 4, "3/4", -65), (7, "64-QAM", 6, 5 / 6, "5/6", -64),
       (8, "256-QAM", 8, 3 / 4, "3/4", -59), (9, "256-QAM", 8, 5 / 6, "5/6", -57),
       (10, "1024-QAM", 10, 3 / 4, "3/4", -54), (11, "1024-QAM", 10, 5 / 6, "5/6", -52),
       (12, "4096-QAM", 12, 3 / 4, "3/4", None), (13, "4096-QAM", 12, 5 / 6, "5/6", None)]


def phy_rate(std, width, streams):
    """Best-case PHY rate in Mbps (shortest guard interval, highest MCS)."""
    if std.startswith("802.11b"):
        return 11.0
    sc, bits, code, tsym = STD_PARAMS[std]
    width = int(width)
    n = sc.get(width) or (sc[max(sc)] if width > max(sc) else sc[min(sc)])
    return n * bits * code * streams / tsym


def shannon_mbps(bw_mhz, snr_db):
    return bw_mhz * math.log2(1 + 10 ** (snr_db / 10))


def best_mcs(rssi, width):
    """Highest MCS whose width-adjusted sensitivity the RSSI satisfies."""
    pen = 3 * math.log2(max(width, 20) / 20)
    best = None
    for m in MCS:
        if m[5] is not None and rssi >= m[5] + pen:
            best = m
    return best


# --------------------------------------------------------------------------
# MAC / vendor
# --------------------------------------------------------------------------
_OUI_SRC = {
    "Apple": "00:03:93 00:0A:95 00:1C:B3 3C:07:54 F0:18:98 A4:5E:60",
    "Samsung": "00:12:47 00:16:32 8C:77:12 5C:0A:5B",
    "Xiaomi": "64:09:80 28:6C:07 F8:A4:5F 34:CE:00",
    "Huawei": "00:E0:FC 00:9A:CD 28:6E:D4",
    "Intel": "00:1B:21 3C:97:0E 7C:5C:F8",
    "TP-Link": "50:C7:BF 14:CC:20 A4:2B:B0 98:DA:C4 C0:25:E9 B0:BE:76 EC:08:6B 18:A6:F7 10:FE:ED",
    "Linksys": "00:14:BF 00:1D:7E C8:D7:19",
    "Netgear": "00:14:6C 00:1F:33 00:22:3F A0:21:B7 2C:30:33",
    "D-Link": "00:05:5D 00:13:46 1C:7E:E5 28:10:7B B8:A3:86",
    "ASUS": "00:11:2F 00:1A:92 04:D9:F5 2C:56:DC 30:5A:3A AC:22:0B",
    "Ubiquiti": "04:18:D6 24:5A:4C 44:D9:E7 78:8A:20 F0:9F:C2 FC:EC:DA 80:2A:A8 74:83:C2",
    "MikroTik": "4C:5E:0C 64:D1:54 6C:3B:6B B8:69:F4 CC:2D:E0 E4:8D:8C",
    "Cisco": "00:00:0C 00:40:96",
    "Aruba": "00:0B:86 24:DE:C6",
    "Zyxel": "00:13:49 00:A0:C5",
    "Tenda": "C8:3A:35",
    "Espressif (ESP IoT)": "24:0A:C4 24:6F:28 30:AE:A4 84:0D:8E A4:CF:12 CC:50:E3",
    "Raspberry Pi": "B8:27:EB DC:A6:32 E4:5F:01 28:CD:C1",
    "Google / Nest": "F4:F5:D8 3C:5A:B4 54:60:09 18:B4:30",
    "Amazon": "74:C2:46 44:65:0D FC:65:DE 68:54:FD",
    "Philips Hue": "00:17:88",
    "VMware": "00:50:56 00:0C:29 00:05:69",
    "VirtualBox": "08:00:27",
    "Microsoft Hyper-V": "00:15:5D",
}
OUI = {p.upper(): v for v, ps in _OUI_SRC.items() for p in ps.split()}
NET_GEAR = {"TP-Link", "Linksys", "Netgear", "D-Link", "ASUS", "Ubiquiti", "MikroTik",
            "Cisco", "Aruba", "Zyxel", "Tenda", "Huawei"}
IOT = {"Espressif (ESP IoT)", "Raspberry Pi", "Google / Nest", "Amazon", "Philips Hue"}
VIRT = {"VMware", "VirtualBox", "Microsoft Hyper-V"}
PHONE_PC = {"Apple", "Samsung", "Xiaomi", "Intel"}
TYPE_WATTS = {"Router (gateway)": 12, "Network gear": 10, "IoT / smart device": 3,
              "Phone / laptop": 15, "Virtual machine": 0, "Unknown": 10}


def norm_mac(m):
    parts = re.split(r"[:\-]", m.strip())
    return ":".join(p.zfill(2) for p in parts).upper() if len(parts) == 6 else m.upper()


def mac_info(mac, extra=None):
    """(vendor, address kind) for a MAC. Built-in OUI list is limited/approximate."""
    try:
        first = int(mac[:2], 16)
    except ValueError:
        return "-", "-"
    prefix = mac[:8].upper()
    local = bool(first & 2)
    kind = ("Locally administered (private / randomised / virtual)" if local
            else "Globally unique (manufacturer assigned)")
    vendor = (extra or {}).get(prefix) or OUI.get(prefix)
    if not vendor:
        vendor = "Unknown (private address)" if local else "Unknown (not in built-in list)"
    return vendor, kind


def guess_type(vendor, mac, is_gw):
    if is_gw:
        return "Router (gateway)"
    if vendor in NET_GEAR:
        return "Network gear"
    if vendor in IOT:
        return "IoT / smart device"
    if vendor in VIRT:
        return "Virtual machine"
    if vendor in PHONE_PC:
        return "Phone / laptop"
    try:
        if int(mac[:2], 16) & 2:
            return "Phone / laptop"
    except ValueError:
        pass
    return "Unknown"


def ttl_guess(ttl):
    if ttl is None:
        return "-"
    if ttl <= 64:
        return "Linux / Android / iOS / macOS / router firmware (TTL<=64)"
    if ttl <= 128:
        return "Windows (TTL<=128)"
    return "Network device, e.g. Cisco (TTL<=255)"


# --------------------------------------------------------------------------
# network probing
# --------------------------------------------------------------------------
def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "-"
    finally:
        s.close()


def gateway_and_dns():
    gw, dns = "-", []
    if IS_WIN:
        txt = run(["route", "print", "-4", "0.0.0.0"])
        rows = re.findall(r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s+\d+\.\d+\.\d+\.\d+\s+(\d+)", txt, re.M)
        if rows:
            gw = min(rows, key=lambda r: int(r[1]))[0]
        dns = re.findall(r"DNS Servers[ .]*:\s*(\d+\.\d+\.\d+\.\d+)", run(["ipconfig", "/all"]))
    elif IS_LINUX:
        m = re.search(r"default via (\S+)", run(["ip", "route", "show", "default"]))
        gw = m.group(1) if m else "-"
        try:
            with open("/etc/resolv.conf") as f:
                dns = re.findall(r"^nameserver\s+(\S+)", f.read(), re.M)
        except Exception:
            pass
    elif IS_MAC:
        m = re.search(r"gateway:\s*(\S+)", run(["route", "-n", "get", "default"]))
        gw = m.group(1) if m else "-"
        dns = re.findall(r"nameserver\[\d+\]\s*:\s*(\S+)", run(["scutil", "--dns"]))
    return gw, list(dict.fromkeys(dns))


def adapter_block(ip):
    """Raw ipconfig /all fields of the adapter that owns `ip` (Windows only)."""
    if not IS_WIN or ip == "-":
        return {}
    for b in re.split(r"\r?\n(?=\S)", run(["ipconfig", "/all"])):
        if ip in b:
            d = {}
            for line in b.splitlines()[1:]:
                m = re.match(r"\s+(.+?)[ .]*:\s*(.*)$", line)
                if m:
                    d.setdefault(m.group(1).strip(), m.group(2).strip())
            return d
    return {}


def lan_network(ip):
    mask = "255.255.255.0"
    if psutil:
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family == socket.AF_INET and a.address == ip and a.netmask:
                    mask = a.netmask
    try:
        net = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
    except ValueError:
        net = ipaddress.ip_network(f"{ip}/24", strict=False)
    if net.num_addresses > 1024:
        net = ipaddress.ip_network(f"{ip}/24", strict=False)
    return net, mask


def own_mac(ip):
    if psutil:
        for addrs in psutil.net_if_addrs().values():
            if any(a.family == socket.AF_INET and a.address == ip for a in addrs):
                for a in addrs:
                    if a.family == psutil.AF_LINK:
                        return norm_mac(a.address)
    n = f"{uuid.getnode():012x}"
    return ":".join(n[i:i + 2] for i in range(0, 12, 2)).upper()


def ping_once(ip, wait_ms=500):
    if IS_WIN:
        cmd = ["ping", "-n", "1", "-w", str(wait_ms), ip]
    elif IS_MAC:
        cmd = ["ping", "-c", "1", "-W", str(wait_ms), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, wait_ms // 1000)), ip]
    out = run(cmd, timeout=4)
    m = re.search(r"time[=<]\s*([\d.]+)\s*ms", out, re.I)
    t = re.search(r"ttl[=:]\s*(\d+)", out, re.I)
    return bool(m or t), (float(m.group(1)) if m else None), (int(t.group(1)) if t else None)


def ping_host(host, count=4):
    if IS_WIN:
        cmd = ["ping", "-n", str(count), "-w", "2000", host]
    elif IS_MAC:
        cmd = ["ping", "-c", str(count), "-W", "2000", host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]
    out = run(cmd, timeout=count * 3 + 6)
    res = dict(host=host, avg=None, min=None, max=None, loss=100.0)
    if IS_WIN:
        m = re.search(r"Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms", out)
        if m:
            res.update(min=float(m.group(1)), max=float(m.group(2)), avg=float(m.group(3)))
        m = re.search(r"\((\d+)% loss\)", out)
    else:
        m = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)", out)
        if m:
            res.update(min=float(m.group(1)), avg=float(m.group(2)), max=float(m.group(3)))
        m = re.search(r"([\d.]+)% packet loss", out)
    if m and "loss" in out:
        res["loss"] = float(m.group(1)) if not IS_WIN or "% loss" in out else res["loss"]
    return res


def parse_arp(txt):
    out = {}
    for line in txt.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)[^\n]*?\b([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})\b", line)
        if m:
            mac = norm_mac(m.group(2))
            if mac != "FF:FF:FF:FF:FF:FF" and not mac.startswith("01:00:5E"):
                out[m.group(1)] = mac
    return out


def read_arp():
    txt = run(["arp", "-a"] if IS_WIN else ["arp", "-an"])
    if not txt.strip() and IS_LINUX:
        txt = run(["ip", "neigh"])
    return parse_arp(txt)


def rdns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


PORTS = {21: "FTP", 22: "SSH", 23: "Telnet", 53: "DNS", 80: "HTTP", 443: "HTTPS",
         5000: "UPnP / web", 7547: "TR-069 (ISP management)", 8080: "HTTP-alt",
         8291: "MikroTik Winbox", 8443: "HTTPS-alt", 8888: "HTTP-alt"}

PORTS_EXT = {
    **PORTS,
    25: "SMTP",
    110: "POP3",
    135: "MS RPC",
    139: "NetBIOS",
    445: "SMB",
    554: "RTSP (camera)",
    1883: "MQTT",
    3389: "RDP",
    5900: "VNC",
    9100: "Printer (JetDirect)",
}



def port_scan(ip, ports=None, timeout=0.6):
    ports = ports or PORTS

    def probe(p):
        s = socket.socket()
        s.settimeout(timeout)
        try:
            return p, s.connect_ex((ip, p)) == 0
        except Exception:
            return p, False
        finally:
            s.close()
    with cf.ThreadPoolExecutor(24) as ex:
        res = list(ex.map(probe, list(ports)))
    return [p for p, ok in res if ok]


def http_probe(ip, ports):
    import urllib.error
    import urllib.request
    info = {}
    for scheme, port in (("http", 80), ("https", 443), ("http", 8080), ("https", 8443)):
        if port not in ports:
            continue
        url = f"{scheme}://{ip}:{port}/"
        ctx = ssl._create_unverified_context() if scheme == "https" else None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AniketWiFiDig"})
            r = urllib.request.urlopen(req, timeout=3, context=ctx)
            hdr, body = r.headers, r.read(4096).decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            hdr = e.headers
            try:
                body = e.read(4096).decode("utf-8", "ignore")
            except Exception:
                body = ""
        except Exception:
            continue
        info["Admin page probed"] = url
        if hdr.get("Server"):
            info["HTTP Server header"] = hdr["Server"]
        if hdr.get("WWW-Authenticate"):
            info["Login realm (often shows model)"] = hdr["WWW-Authenticate"]
        m = re.search(r"<title>(.*?)</title>", body, re.I | re.S)
        if m:
            info["Admin page title"] = " ".join(m.group(1).split())[:90]
        break
    return info


def lan_scan(extra_oui):
    lip = local_ip()
    gw, _ = gateway_and_dns()
    net, mask = lan_network(lip)
    hosts = [str(h) for h in net.hosts()]
    alive = {}
    with cf.ThreadPoolExecutor(64) as ex:
        futs = {ex.submit(ping_once, h, 400): h for h in hosts}
        for f in cf.as_completed(futs):
            ok, ms, ttl = f.result()
            if ok:
                alive[futs[f]] = (ms, ttl)
    arp = read_arp()
    ips = set(alive) | {ip for ip in arp if ipaddress.ip_address(ip) in net} | {lip}
    ex = cf.ThreadPoolExecutor(32)
    futs = {ex.submit(rdns, ip): ip for ip in ips}
    done, _ = cf.wait(futs, timeout=6)
    names = {futs[f]: f.result() for f in done}
    ex.shutdown(wait=False, cancel_futures=True)
    devs = []
    for ip in sorted(ips, key=lambda x: tuple(int(p) for p in x.split("."))):
        mac = own_mac(ip) if ip == lip else arp.get(ip, "-")
        vendor, kind = mac_info(mac, extra_oui) if mac != "-" else ("-", "-")
        ms, ttl = alive.get(ip, (None, None))
        devs.append(dict(ip=ip, mac=mac, vendor=vendor, kind=kind, host=names.get(ip, ""),
                         ms=ms, os=ttl_guess(ttl), me=(ip == lip), gw=(ip == gw),
                         type=guess_type(vendor, mac, ip == gw)))
    return devs, f"{net} (mask {mask}), {len(hosts)} addresses swept"


# --------------------------------------------------------------------------
# Wi-Fi
# --------------------------------------------------------------------------
def get_wifi():
    info = dict(connected=False, ssid="-", bssid="-", signal=None, rssi=None, channel=None,
                band="-", security="-", link="-", radio="-", details={})
    if IS_WIN:
        d = {}
        for line in run(["netsh", "wlan", "show", "interfaces"]).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if k == "Name" and "Name" in d:
                    break
                if k and k not in d:
                    d[k] = v
        if d:
            sig = d.get("Signal", "").strip("%")
            info["signal"] = int(sig) if sig.isdigit() else None
            if info["signal"] is not None:
                info["rssi"] = int(info["signal"] / 2 - 100)
            ch = d.get("Channel", "")
            info["channel"] = int(ch) if ch.isdigit() else None
            info.update(band=band_of(info["channel"]), ssid=d.get("SSID", "-") or "-",
                        bssid=d.get("BSSID") or d.get("AP BSSID") or "-",
                        security=d.get("Authentication", "-"), radio=d.get("Radio type", "-"),
                        link=f"{d.get('Receive rate (Mbps)', '?')} down / {d.get('Transmit rate (Mbps)', '?')} up Mbps",
                        connected=d.get("State", "").lower() == "connected", details=d)
    elif IS_LINUX:
        out = run(["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,CHAN,FREQ,RATE,SIGNAL,SECURITY", "dev", "wifi"])
        for line in out.splitlines():
            p = [x.replace("\\:", ":") for x in re.split(r"(?<!\\):", line)]
            if len(p) >= 8 and p[0] == "yes":
                sig = int(p[6]) if p[6].isdigit() else None
                info.update(connected=True, ssid=p[1] or "-", bssid=p[2],
                            channel=int(p[3]) if p[3].isdigit() else None, link=p[5],
                            signal=sig, rssi=int(sig / 2 - 100) if sig is not None else None,
                            security=p[7] or "Open")
                info["band"] = band_of(info["channel"])
                info["details"] = {"SSID": p[1], "BSSID": p[2], "Channel": p[3], "Frequency": p[4],
                                   "Rate": p[5], "Signal": f"{p[6]}%", "Security": p[7]}
                break
    elif IS_MAC:
        ap = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        d = {}
        for line in run([ap, "-I"]).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip()
        if d.get("SSID"):
            rssi = int(d["agrCtlRSSI"]) if d.get("agrCtlRSSI", "").lstrip("-").isdigit() else None
            ch = re.match(r"(\d+)", d.get("channel", ""))
            info.update(connected=True, ssid=d["SSID"], bssid=d.get("BSSID", "-"), rssi=rssi,
                        signal=clamp(2 * (rssi + 100), 0, 100) if rssi is not None else None,
                        channel=int(ch.group(1)) if ch else None, security=d.get("link auth", "-"),
                        link=f"{d.get('lastTxRate', '?')} Mbps", details=d)
            info["band"] = band_of(info["channel"])
    return info


def scan_nearby():
    nets = []
    if IS_WIN:
        ssid, auth, bss = "", "", None
        for line in run(["netsh", "wlan", "show", "networks", "mode=bssid"], 30).splitlines():
            s = line.strip()
            m = re.match(r"SSID\s+\d+\s*:\s*(.*)", s)
            if m:
                ssid, auth, bss = m.group(1) or "(hidden)", "", None
                continue
            m = re.match(r"Authentication\s*:\s*(.*)", s)
            if m and bss is None:
                auth = m.group(1)
                continue
            m = re.match(r"BSSID\s+\d+\s*:\s*(.*)", s)
            if m:
                bss = dict(ssid=ssid, bssid=m.group(1), security=auth, signal=0, channel=None)
                nets.append(bss)
                continue
            if bss is not None:
                m = re.match(r"Signal\s*:\s*(\d+)%", s)
                if m:
                    bss["signal"] = int(m.group(1))
                m = re.match(r"Channel\s*:\s*(\d+)", s)
                if m:
                    bss["channel"] = int(m.group(1))
    elif IS_LINUX:
        out = run(["nmcli", "-t", "-f", "SSID,BSSID,CHAN,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"], 30)
        for line in out.splitlines():
            p = [x.replace("\\:", ":") for x in re.split(r"(?<!\\):", line)]
            if len(p) >= 5:
                nets.append(dict(ssid=p[0] or "(hidden)", bssid=p[1],
                                 channel=int(p[2]) if p[2].isdigit() else None,
                                 signal=int(p[3]) if p[3].isdigit() else 0, security=p[4] or "Open"))
    elif IS_MAC:
        ap = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        rx = re.compile(r"^\s*(.*?)\s+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\s+(-?\d+)\s+(\d+)\S*\s+\S+\s+\S+\s+(.*)$")
        for line in run([ap, "-s"], 30).splitlines()[1:]:
            m = rx.match(line)
            if m:
                nets.append(dict(ssid=m.group(1) or "(hidden)", bssid=m.group(2),
                                 signal=clamp(2 * (int(m.group(3)) + 100), 0, 100),
                                 channel=int(m.group(4)), security=m.group(5)))
    for n in nets:
        n["band"] = band_of(n["channel"])
    nets.sort(key=lambda n: n["signal"], reverse=True)
    return nets


def best_channels(nets):
    c24 = [n for n in nets if n["channel"] and n["channel"] <= 14]
    c5 = [n for n in nets if n["channel"] and n["channel"] >= 36]
    l24 = lambda c: sum(n["signal"] * max(0, 1 - abs(n["channel"] - c) / 5) for n in c24)
    l5 = lambda c: sum(n["signal"] for n in c5 if n["channel"] == c)
    return {"2.4 GHz": min((1, 6, 11), key=l24),
            "5 GHz": min((36, 40, 44, 48, 149, 153, 157, 161), key=l5)}


# --------------------------------------------------------------------------
# router probe (runs in a worker thread)
# --------------------------------------------------------------------------
def probe_router(S, noise):
    w = get_wifi()
    gw, dns = gateway_and_dns()
    lip = local_ip()
    sec, finds = {}, []
    ident = {"Gateway (router) IP": gw}
    gp = None
    ports = []
    if gw != "-":
        gp = ping_host(gw, 8)
        ports = port_scan(gw)
        mac = read_arp().get(gw, "-")
        vendor, kind = mac_info(mac, S["oui_extra"]) if mac != "-" else ("-", "-")
        _, _, ttl = ping_once(gw)
        ident.update({"MAC address": mac, "Vendor (OUI, approx.)": vendor, "Address type": kind,
                      "Hostname (reverse DNS)": rdns(gw) or "-",
                      "Firmware family (TTL guess)": ttl_guess(ttl)})
        ident.update(http_probe(gw, ports))
    sec["Router identity"] = ident

    if gp:
        lat = {"Round-trip min / avg / max": "no reply" if gp["avg"] is None else
               f"{gp['min']:.0f} / {gp['avg']:.0f} / {gp['max']:.0f} ms",
               "Packet loss (8 pings)": f"{gp['loss']:.0f}%"}
        if gp["avg"] is not None:
            lat["Jitter (max - min)"] = f"{gp['max'] - gp['min']:.0f} ms"
        sec["Reachability"] = lat
        if gp["avg"] is None:
            finds.append(("bad", "Router did not answer ping (ICMP may be blocked)."))
        else:
            if gp["avg"] > 10:
                finds.append(("warn", f"Router latency is {gp['avg']:.0f} ms; a healthy LAN is usually under 5 ms."))
            if gp["loss"] > 0:
                finds.append(("bad", f"{gp['loss']:.0f}% packet loss to the router: check signal, cable or interference."))
            if gp["avg"] <= 10 and gp["loss"] == 0:
                finds.append(("good", "Router responds quickly with no packet loss."))

    svc = {"Open TCP ports": ", ".join(f"{p} ({PORTS[p]})" for p in ports) or "none found among common ports"}
    sec["Services on router"] = svc
    if 23 in ports:
        finds.append(("bad", "Telnet (23) is open: unencrypted remote console. Disable it and use SSH."))
    if 21 in ports:
        finds.append(("warn", "FTP (21) is open on the router; disable unless needed."))
    if 80 in ports and 443 not in ports:
        finds.append(("warn", "Router admin is reachable over plain HTTP only (no HTTPS)."))
    if 7547 in ports:
        finds.append(("warn", "TR-069 (7547) reachable: ISP remote-management service; make sure it is not exposed to the internet."))

    blk = adapter_block(lip)
    addr = {"Local IP": lip, "DNS servers": ", ".join(dns) or "-"}
    net, mask = lan_network(lip) if lip != "-" else (None, "-")
    addr["Subnet mask"] = blk.get("Subnet Mask", mask)
    if net:
        addr["Network / usable hosts"] = f"{net} / {max(net.num_addresses - 2, 0)}"
    for k in ("Description", "Physical Address", "DHCP Enabled", "DHCP Server", "Lease Obtained", "Lease Expires"):
        if k in blk:
            addr[k] = blk[k]
    sec["Addressing & DHCP"] = addr

    rad = {}
    if w["connected"]:
        std = w["radio"]
        rad["SSID"] = w["ssid"]
        rad["BSSID"] = w["bssid"]
        rad["BSSID vendor (approx.)"] = mac_info(norm_mac(w["bssid"]), S["oui_extra"])[0] if ":" in w["bssid"] or "-" in w["bssid"] else "-"
        rad["Wi-Fi generation"] = f"{std}  ({GEN_NAMES.get(std, 'unknown')})"
        rad["Band / channel"] = f"{w['band']} / ch {w['channel']}  ({center_mhz(w['channel'])} MHz centre)"
        rad["Security"] = w["security"]
        rad["Link rate"] = w["link"]
        if w["rssi"] is not None:
            snr = w["rssi"] - noise
            width = 20 if (w["channel"] or 0) <= 14 else 80
            rad["Signal"] = f"{w['signal']}%  ≈ {w['rssi']} dBm  ({rssi_quality(w['rssi'])})"
            rad["Assumed noise floor"] = f"{noise} dBm (not measurable from the OS)"
            rad["Estimated SNR"] = f"{snr:.0f} dB"
            rad[f"Shannon limit / stream @ {width} MHz"] = f"{shannon_mbps(width, snr):.0f} Mbps (theoretical)"
            m = best_mcs(w["rssi"], width)
            rad["Highest sustainable MCS (by RSSI)"] = (f"MCS {m[0]} = {m[1]} {m[4]}" if m else "below MCS 0 sensitivity")
            r = S["router"]
            eirp = r["tx_dbm"] + r["ant_gain"] - r["cable_loss"] if r["tx_dbm"] else 20.0
            f = center_mhz(w["channel"])
            if f:
                pl = eirp - w["rssi"]
                d = 10 ** ((pl - 32.44 - 20 * math.log10(f)) / 20) * 1000
                note = "" if r["tx_dbm"] else " (assumes 20 dBm EIRP)"
                rad["Free-space distance equivalent"] = f"≈ {d:.0f} m of open air; walls shorten this{note}"
            if w["signal"] is not None and w["signal"] < 40:
                finds.append(("bad", f"Weak signal ({w['signal']}%). Move closer or add an access point."))
            elif w["signal"] is not None and w["signal"] < 60:
                finds.append(("warn", f"Moderate signal ({w['signal']}%)."))
        if "2.4" in w["band"]:
            finds.append(("warn", "Connected on 2.4 GHz: congested and slow. Prefer 5 GHz where possible."))
        sc = (w["security"] or "").lower()
        if sc in ("open", "none", ""):
            finds.append(("bad", "Open Wi-Fi: no encryption."))
        elif "wep" in sc or sc in ("wpa-personal", "wpa"):
            finds.append(("warn", f"Legacy Wi-Fi security ({w['security']}). Use WPA2-AES or WPA3."))
        else:
            finds.append(("good", f"Wi-Fi security: {w['security']}."))
    else:
        rad["Status"] = "Not on Wi-Fi (wired) or Wi-Fi details unavailable on this OS"
    sec["Wi-Fi radio (connected AP)"] = rad
    sec["Findings"] = {str(i + 1): f"[{lvl.upper()}] {t}" for i, (lvl, t) in enumerate(finds)}
    if w["details"]:
        sec["Raw Wi-Fi adapter report"] = w["details"]
    if blk:
        sec["Raw IP configuration (ipconfig)"] = blk
    return sec, w


def router_spec_section(S):
    r = S["router"]
    if not r["model"] and not r["price"]:
        return {"Status": "No spec sheet yet: click 'Edit router specs…' to add model, power, antennas and price"}
    eirp = r["tx_dbm"] + r["ant_gain"] - r["cable_loss"]
    mw = 10 ** (eirp / 10)
    rate = phy_rate(r["standard"], r["width"], int(r["streams"]))
    kwh = r["watts"] * r["hours"] * 30 / 1000
    return {
        "Model": r["model"] or "-", "Standard": r["standard"],
        "Channel width / spatial streams": f"{r['width']} MHz / {int(r['streams'])}",
        "Max PHY rate (computed, per band)": f"{rate:,.0f} Mbps",
        "Tx power / antenna gain / cable loss": f"{r['tx_dbm']} dBm / {r['ant_gain']} dBi / {r['cable_loss']} dB",
        "EIRP": f"{eirp:.1f} dBm = {mw:,.0f} mW  (ERP {eirp - 2.15:.1f} dBm)",
        "Typical legal EIRP limits": "2.4 GHz: 20 dBm (ETSI) / 36 dBm (FCC); 5 GHz varies by band and region",
        "Purchase price": f"{S['currency']}{r['price']:,.2f}",
        "Power draw / hours per day": f"{r['watts']} W / {r['hours']} h",
        "Energy per month": f"{kwh:.2f} kWh",
        "Electricity per month / year": f"{S['currency']}{kwh * S['tariff']:.2f} / {S['currency']}{kwh * S['tariff'] * 12:.2f}",
        "Purchased": r["purchased"] or "-", "Notes": r["notes"] or "-",
    }


# --------------------------------------------------------------------------
# calculators
# --------------------------------------------------------------------------
CALCS = []


def calc(name, desc, fields):
    def deco(fn):
        CALCS.append((name, desc, fields, fn))
        return fn
    return deco


def need(v, *keys):
    for k in keys:
        if v.get(k) is None:
            raise ValueError("Please fill in all the fields.")
    return [v[k] for k in keys]


def lg(x):
    if x <= 0:
        raise ValueError("Value must be greater than zero.")
    return math.log10(x)


@calc("dBm ⇄ mW ⇄ W", "dBm = 10·log10(P / 1 mW). Fill dBm, or mW to convert the other way.",
      [("dbm", "Power (dBm)", "20"), ("mw", "…or power (mW) - overrides dBm", "")])
def _c_dbm(v):
    if v["mw"] is not None:
        mw = v["mw"]
        dbm = 10 * lg(mw)
    else:
        dbm = need(v, "dbm")[0]
        mw = 10 ** (dbm / 10)
    return [("Power", f"{dbm:.2f} dBm"), ("Power", f"{mw:.6g} mW"),
            ("Power", f"{mw / 1000:.6g} W"), ("Power", f"{dbm - 30:.2f} dBW")]


@calc("Free-space path loss", "FSPL = 20·log10(d km) + 20·log10(f MHz) + 32.44 dB;  λ = c / f;  first Fresnel radius at midpoint r = ½·√(λ·d).",
      [("f", "Frequency (MHz)", "2437"), ("d", "Distance (m)", "30")])
def _c_fspl(v):
    f, d = need(v, "f", "d")
    lam = 299.792458 / f
    return [("Free-space path loss", f"{20 * lg(d / 1000) + 20 * lg(f) + 32.44:.2f} dB"),
            ("Loss at 1 m reference", f"{20 * lg(f) - 27.55:.2f} dB"),
            ("Wavelength λ", f"{lam * 100:.2f} cm"), ("Quarter-wave antenna", f"{lam * 25:.2f} cm"),
            ("1st Fresnel zone radius (midpoint)", f"{0.5 * math.sqrt(lam * d):.2f} m"),
            ("Keep clear (60% rule)", f"{0.6 * 0.5 * math.sqrt(lam * d):.2f} m")]


@calc("Indoor path loss & RSSI", "Log-distance model: PL = FSPL(1 m) + 10·n·log10(d) + walls·Lw. n ≈ 2 open space, 3-4 offices, 4-6 dense walls.",
      [("f", "Frequency (MHz)", "2437"), ("d", "Distance (m)", "15"), ("n", "Path-loss exponent n", "3"),
       ("walls", "Number of walls", "2"), ("lw", "Loss per wall (dB)", "5"),
       ("eirp", "Transmit EIRP (dBm)", "20"), ("grx", "Receiver antenna gain (dBi)", "0")])
def _c_indoor(v):
    f, d, n, walls, lw, eirp, grx = need(v, "f", "d", "n", "walls", "lw", "eirp", "grx")
    pl = 20 * lg(f) - 27.55 + 10 * n * lg(max(d, 1)) + walls * lw
    rx = eirp - pl + grx
    return [("Total path loss", f"{pl:.1f} dB"), ("Predicted RSSI", f"{rx:.1f} dBm"),
            ("Quality", rssi_quality(rx))]


@calc("Link budget & fade margin", "Rx = Ptx + Gtx − Ltx − FSPL + Grx − Lrx;  fade margin = Rx − sensitivity.",
      [("ptx", "Tx power (dBm)", "20"), ("gtx", "Tx antenna gain (dBi)", "5"), ("ltx", "Tx cable loss (dB)", "0.5"),
       ("f", "Frequency (MHz)", "5180"), ("d", "Distance (m)", "100"), ("grx", "Rx antenna gain (dBi)", "2"),
       ("lrx", "Rx cable loss (dB)", "0"), ("sens", "Rx sensitivity (dBm)", "-72")])
def _c_link(v):
    ptx, gtx, ltx, f, d, grx, lrx, sens = need(v, "ptx", "gtx", "ltx", "f", "d", "grx", "lrx", "sens")
    eirp = ptx + gtx - ltx
    fspl = 20 * lg(d / 1000) + 20 * lg(f) + 32.44
    rx = eirp - fspl + grx - lrx
    allowed = eirp + grx - lrx - sens
    dmax = 10 ** ((allowed - 32.44 - 20 * lg(f)) / 20) * 1000
    margin = rx - sens
    return [("EIRP", f"{eirp:.1f} dBm ({10 ** (eirp / 10):.0f} mW)"), ("Free-space path loss", f"{fspl:.1f} dB"),
            ("Received power", f"{rx:.1f} dBm"), ("Fade margin", f"{margin:.1f} dB"),
            ("Verdict", "Solid link (≥10 dB)" if margin >= 10 else "Marginal (<10 dB)" if margin >= 0 else "Link will fail"),
            ("Max free-space range", f"{dmax:,.0f} m")]


@calc("SNR & Shannon capacity", "SNR = signal − noise floor.  C = B·log2(1 + SNR). Real Wi-Fi reaches roughly 50-70% of the limit.",
      [("rssi", "Signal / RSSI (dBm)", "-60"), ("noise", "Noise floor (dBm)", "-95"), ("bw", "Channel width (MHz)", "80")])
def _c_snr(v):
    rssi, noise, bw = need(v, "rssi", "noise", "bw")
    snr = rssi - noise
    cap = shannon_mbps(bw, snr)
    m = best_mcs(rssi, bw)
    return [("SNR", f"{snr:.1f} dB"), ("Shannon capacity / stream", f"{cap:,.0f} Mbps"),
            ("Realistic (≈60%)", f"{cap * 0.6:,.0f} Mbps"),
            ("Highest MCS by sensitivity", f"MCS {m[0]} ({m[1]} {m[4]})" if m else "below MCS 0")]


@calc("Thermal noise floor", "N = k·T·B → −174 dBm/Hz + 10·log10(B) + NF (at 290 K). Sets the lowest signal a receiver can use.",
      [("bw", "Bandwidth (MHz)", "20"), ("nf", "Receiver noise figure (dB)", "5"), ("t", "Temperature (K)", "290")])
def _c_noise(v):
    bw, nf, t = need(v, "bw", "nf", "t")
    kt = 10 * lg(1.380649e-23 * t * bw * 1e6 / 1e-3)
    return [("Thermal noise (kTB)", f"{kt:.1f} dBm"), ("Receiver noise floor", f"{kt + nf:.1f} dBm"),
            ("Density", f"{10 * lg(1.380649e-23 * t / 1e-3):.1f} dBm/Hz")]


@calc("Wi-Fi PHY rate", "Rate = streams × data subcarriers × bits/symbol × coding rate ÷ symbol time (best case, shortest guard interval).",
      [("std", "Standard", list(STD_PARAMS)[3], list(STD_PARAMS) + ["802.11b"]),
       ("width", "Channel width (MHz)", "80", ["20", "40", "80", "160", "320"]),
       ("ss", "Spatial streams", "2", ["1", "2", "3", "4", "8"])])
def _c_phy(v):
    r = phy_rate(v["std"], v["width"], int(v["ss"]))
    return [("Max PHY rate", f"{r:,.1f} Mbps"), ("Realistic throughput (≈55%)", f"{r * 0.55:,.0f} Mbps"),
            ("Per-stream rate", f"{r / int(v['ss']):,.1f} Mbps")]


@calc("EIRP / ERP", "EIRP = Ptx + Gant − Lcable.  ERP = EIRP − 2.15 dB (referenced to a dipole).",
      [("p", "Tx power (dBm)", "20"), ("g", "Antenna gain (dBi)", "3"), ("l", "Cable / connector loss (dB)", "0")])
def _c_eirp(v):
    p, g, l = need(v, "p", "g", "l")
    e = p + g - l
    return [("EIRP", f"{e:.2f} dBm = {10 ** (e / 10):,.1f} mW"), ("ERP", f"{e - 2.15:.2f} dBm"),
            ("Reference", "ETSI 2.4 GHz limit 20 dBm; FCC point-to-multipoint 36 dBm")]


@calc("VSWR / return loss / mismatch", "Γ = (VSWR − 1)/(VSWR + 1);  RL = −20·log10 Γ;  mismatch loss = −10·log10(1 − Γ²).",
      [("s", "VSWR (≥ 1)", "1.5")])
def _c_vswr(v):
    s = need(v, "s")[0]
    if s < 1:
        raise ValueError("VSWR must be 1 or higher.")
    g = (s - 1) / (s + 1)
    return [("Reflection coefficient Γ", f"{g:.4f}"),
            ("Return loss", "∞ dB (perfect match)" if g == 0 else f"{-20 * math.log10(g):.2f} dB"),
            ("Mismatch loss", f"{-10 * math.log10(1 - g * g):.3f} dB"), ("Power reflected", f"{g * g * 100:.2f}%")]


@calc("Ohm's law & power", "V = I·R and P = V·I. Fill any two values; the rest are calculated.",
      [("v", "Voltage V (volts)", ""), ("i", "Current I (amps)", ""), ("r", "Resistance R (ohms)", ""), ("p", "Power P (watts)", "")])
def _c_ohm(v):
    V, I, R, P = v["v"], v["i"], v["r"], v["p"]
    if sum(x is not None for x in (V, I, R, P)) < 2:
        raise ValueError("Enter at least two values.")
    if V is not None and I is not None:
        R, P = V / I, V * I
    elif V is not None and R is not None:
        I, P = V / R, V * V / R
    elif V is not None and P is not None:
        I, R = P / V, V * V / P
    elif I is not None and R is not None:
        V, P = I * R, I * I * R
    elif I is not None and P is not None:
        V, R = P / I, P / (I * I)
    else:
        V, I = math.sqrt(P * R), math.sqrt(P / R)
    return [("Voltage", f"{V:.4g} V"), ("Current", f"{I:.4g} A"), ("Resistance", f"{R:.4g} Ω"), ("Power", f"{P:.4g} W")]


@calc("Electricity cost of a device", "Energy (kWh) = watts × hours ÷ 1000. Cost = kWh × tariff.",
      [("w", "Power draw (watts)", "12"), ("h", "Hours per day", "24"), ("q", "Quantity", "1"), ("tariff", "Tariff (per kWh)", "0.12")])
def _c_energy(v):
    w, h, q, t = need(v, "w", "h", "q", "tariff")
    kd = w * h * q / 1000
    return [("Energy per day", f"{kd:.3f} kWh"), ("Energy per month (30 d)", f"{kd * 30:.2f} kWh"),
            ("Energy per year", f"{kd * 365:.1f} kWh"), ("Cost per month", f"{kd * 30 * t:,.2f}"),
            ("Cost per year", f"{kd * 365 * t:,.2f}")]


POE = {"802.3af (Type 1, PoE)": (15.4, 12.95, 44, 2), "802.3at (Type 2, PoE+)": (30.0, 25.5, 50, 2),
       "802.3bt (Type 3, PoE++)": (60.0, 51.0, 50, 4), "802.3bt (Type 4, PoE++)": (90.0, 71.3, 52, 4)}


@calc("PoE cable loss", "I = Ppse / Vpse(min);  Rloop = 2·r·L / pairs;  loss = I²·Rloop. Cat5e DC resistance ≈ 0.0938 Ω/m per conductor (TIA max).",
      [("std", "PoE standard", list(POE)[1], list(POE)), ("len", "Cable length (m)", "100"), ("r", "Resistance per conductor (Ω/m)", "0.0938")])
def _c_poe(v):
    ppse, pspec, vmin, pairs = POE[v["std"]]
    L, r = need(v, "len", "r")
    I = ppse / vmin
    rl = 2 * r * L / pairs
    loss = I * I * rl
    return [("Current", f"{I:.3f} A"), ("Loop resistance", f"{rl:.2f} Ω"), ("Cable loss (I²R)", f"{loss:.2f} W"),
            ("Power at device (estimate)", f"{ppse - loss:.2f} W"), ("Spec-guaranteed at device", f"{pspec} W"),
            ("Efficiency", f"{(ppse - loss) / ppse * 100:.1f}%")]


@calc("PoE switch budget", "Total load must stay within the switch's PoE budget; keep ≈20% headroom.",
      [("n", "Number of PoE devices", "8"), ("w", "Average draw per device (W)", "7"), ("budget", "Switch PoE budget (W)", "65")])
def _c_budget(v):
    n, w, b = need(v, "n", "w", "budget")
    tot = n * w
    return [("Total load", f"{tot:.1f} W"), ("Utilisation", f"{tot / b * 100:.0f}%"), ("Headroom", f"{b - tot:.1f} W"),
            ("Verdict", "OK (≤80%)" if tot <= 0.8 * b else "Tight (80-100%)" if tot <= b else "Over budget")]


@calc("Channel ⇄ frequency", "2.4 GHz: f = 2407 + 5·ch;  5 GHz: f = 5000 + 5·ch;  6 GHz: f = 5950 + 5·ch (MHz).",
      [("band", "Band", "2.4 GHz", ["2.4 GHz", "5 GHz", "6 GHz"]), ("ch", "Channel number", "6")])
def _c_chan(v):
    ch = need(v, "ch")[0]
    f = (2484 if ch == 14 else 2407 + 5 * ch) if v["band"] == "2.4 GHz" else (5000 + 5 * ch if v["band"] == "5 GHz" else 5950 + 5 * ch)
    return [("Centre frequency", f"{f:.0f} MHz"), ("20 MHz channel edges", f"{f - 10:.0f} - {f + 10:.0f} MHz"),
            ("Wavelength", f"{299.792458 / f * 100:.2f} cm")]


@calc("File transfer time", "Time = size × 8 ÷ (link rate × efficiency). Wi-Fi efficiency is typically 50-70%.",
      [("gb", "Data size (GB)", "50"), ("mbps", "Link rate (Mbps)", "866"), ("eff", "Efficiency (%)", "60")])
def _c_transfer(v):
    gb, mb, eff = need(v, "gb", "mbps", "eff")
    sec = gb * 8000 / (mb * eff / 100)
    return [("Effective speed", f"{mb * eff / 100:,.0f} Mbps"),
            ("Transfer time", f"{int(sec // 3600)} h {int(sec % 3600 // 60)} min {int(sec % 60)} s")]


# --------------------------------------------------------------------------
# reference tables
# --------------------------------------------------------------------------
def ref_tables():
    t = {}
    t["Wi-Fi generations"] = (
        ["Standard", "Name", "Year", "Bands", "Channel widths", "Max modulation", "Max streams", "Max PHY rate", "Key technology"],
        [("802.11b", "Wi-Fi 1", "1999", "2.4 GHz", "22 MHz", "DSSS / CCK", "1", "11 Mbps", "Direct-sequence spread spectrum"),
         ("802.11a", "Wi-Fi 2", "1999", "5 GHz", "20 MHz", "64-QAM", "1", "54 Mbps", "First OFDM"),
         ("802.11g", "Wi-Fi 3", "2003", "2.4 GHz", "20 MHz", "64-QAM", "1", "54 Mbps", "OFDM on 2.4 GHz"),
         ("802.11n", "Wi-Fi 4", "2009", "2.4 / 5 GHz", "20 / 40 MHz", "64-QAM", "4", "600 Mbps", "MIMO, frame aggregation"),
         ("802.11ac", "Wi-Fi 5", "2013", "5 GHz", "20-160 MHz", "256-QAM", "8", "6.93 Gbps", "Downlink MU-MIMO, beamforming"),
         ("802.11ax", "Wi-Fi 6 / 6E", "2019", "2.4 / 5 / 6 GHz", "20-160 MHz", "1024-QAM", "8", "9.61 Gbps", "OFDMA, BSS colouring, TWT, UL MU-MIMO"),
         ("802.11be", "Wi-Fi 7", "2024", "2.4 / 5 / 6 GHz", "20-320 MHz", "4096-QAM", "16", "46.1 Gbps", "Multi-Link Operation, multi-RU, 320 MHz")],
        "Max PHY rates are theoretical spec maxima; real throughput is roughly 50-70% of the negotiated rate.")
    t["2.4 GHz channels"] = (
        ["Channel", "Centre (MHz)", "20 MHz span (MHz)", "Overlap"],
        [(c, 2484 if c == 14 else 2407 + 5 * c, f"{(2484 if c == 14 else 2407 + 5 * c) - 10} - {(2484 if c == 14 else 2407 + 5 * c) + 10}",
          "Non-overlapping set (1/6/11)" if c in (1, 6, 11) else ("Japan only, 802.11b" if c == 14 else "Overlaps neighbours")) for c in range(1, 15)],
        "Channels 12-13 are allowed in Europe/most of the world; the US limits to 1-11.")
    rows5 = []
    for band, chs, dfs in (("U-NII-1 (5150-5250)", [36, 40, 44, 48], "No"),
                           ("U-NII-2A (5250-5350)", [52, 56, 60, 64], "Yes (DFS)"),
                           ("U-NII-2C (5470-5725)", list(range(100, 145, 4)), "Yes (DFS)"),
                           ("U-NII-3 (5725-5850)", [149, 153, 157, 161, 165], "No")):
        rows5 += [(c, 5000 + 5 * c, band, dfs) for c in chs]
    t["5 GHz channels"] = (["Channel", "Centre (MHz)", "U-NII band", "Radar / DFS"], rows5,
                           "Availability differs by country. DFS channels may be vacated automatically when radar is detected.")
    t["6 GHz (Wi-Fi 6E / 7)"] = (
        ["U-NII band", "Range (MHz)", "20 MHz channels", "Notes"],
        [("U-NII-5", "5925-6425", "1-93", "Lowest part; widely available"), ("U-NII-6", "6425-6525", "97-113", "Shared with fixed services"),
         ("U-NII-7", "6525-6875", "117-185", "Largest block"), ("U-NII-8", "6875-7125", "189-233", "Top of the band")],
        "Centre frequency = 5950 + 5×channel MHz. US: 59 × 20 MHz, 29 × 40 MHz, 14 × 80 MHz, 7 × 160 MHz channels. Requires WPA3.")
    t["MCS / modulation"] = (
        ["MCS", "Modulation", "Coding rate", "Bits/symbol", "Min sensitivity @20 MHz", "Rate 20 MHz 1SS (HE, 0.8 µs GI)"],
        [(m[0], m[1], m[4], m[2], f"{m[5]} dBm" if m[5] else "n/a", f"{234 * m[2] * m[3] / 13.6:.1f} Mbps") for m in MCS],
        "Sensitivity worsens ~3 dB each time channel width doubles. MCS 12-13 are 802.11be (4096-QAM).")
    t["RSSI quality guide"] = (
        ["RSSI (dBm)", "Quality", "Typical meaning"],
        [("-30", "Maximum", "Standing next to the AP"), ("-50 or better", "Excellent", "Full speed"),
         ("-60", "Very good", "Reliable for streaming and calls"), ("-67", "Good", "Minimum recommended for voice / video"),
         ("-70", "Fair", "Minimum for reliable packet delivery"), ("-80", "Weak", "Basic connectivity, frequent retries"),
         ("-90", "Unusable", "At or below the noise floor")], "Based on common enterprise Wi-Fi design guidance.")
    t["dB cheat sheet"] = (
        ["Change", "Power ratio", "Notes"],
        [("+3 dB", "× 2", "Doubles power"), ("-3 dB", "× 0.5", "Halves power"), ("+6 dB", "× 4", "Doubles free-space range"),
         ("+10 dB", "× 10", ""), ("+20 dB", "× 100", ""), ("0 dBm", "1 mW", "Reference level"), ("10 dBm", "10 mW", ""),
         ("20 dBm", "100 mW", "Typical home router per chain"), ("30 dBm", "1 W", ""), ("36 dBm", "4 W", "FCC 2.4 GHz EIRP ceiling")],
        "dB values add when gains and losses are chained; powers multiply.")
    t["Cabling & Ethernet"] = (
        ["Medium", "Bandwidth", "Typical use", "Max distance"],
        [("Cat5e", "100 MHz", "1 GbE (2.5/5 GbE short runs)", "100 m"), ("Cat6", "250 MHz", "1 GbE; 10 GbE", "100 m (10 GbE: 55 m)"),
         ("Cat6a", "500 MHz", "10 GbE", "100 m"), ("Cat7 (ISO)", "600 MHz", "10 GbE, shielded", "100 m"),
         ("Cat8", "2000 MHz", "25/40 GbE data-centre", "30 m"), ("Multimode OM3 / OM4", "-", "10 GbE (SR)", "300 m / 400 m"),
         ("Single-mode OS2", "-", "10 GbE+ (LR)", "10 km+")], "Twisted-pair Ethernet channel limit is 100 m including patch cords.")
    t["PoE standards"] = (
        ["Standard", "Type", "Power at switch (PSE)", "Power at device (PD)", "Pairs used", "Voltage at PSE"],
        [("802.3af", "1 (PoE)", "15.4 W", "12.95 W", "2", "44-57 V"), ("802.3at", "2 (PoE+)", "30 W", "25.5 W", "2", "50-57 V"),
         ("802.3bt", "3 (PoE++)", "60 W", "51 W", "4", "50-57 V"), ("802.3bt", "4 (PoE++)", "90 W", "71.3 W", "4", "52-57 V")],
        "Cable resistance makes the device receive less than the switch supplies.")
    t["Wi-Fi security"] = (
        ["Protocol", "Encryption", "Authentication", "Status"],
        [("WEP", "RC4", "Shared key", "Broken since 2001; never use"), ("WPA (TKIP)", "RC4 / TKIP", "PSK or 802.1X", "Deprecated"),
         ("WPA2-Personal", "AES-CCMP", "PSK, 4-way handshake", "Acceptable with a long passphrase"),
         ("WPA2-Enterprise", "AES-CCMP", "802.1X / RADIUS", "Good"),
         ("WPA3-Personal", "AES-CCMP / GCMP", "SAE", "Recommended"), ("WPA3-Enterprise", "GCMP-256 (192-bit)", "802.1X", "Strongest"),
         ("OWE (Enhanced Open)", "AES", "None (opportunistic)", "Encrypts open guest networks")], "Disable WPS PIN on all routers.")
    return t


GLOSSARY_RAW = """
dB|RF|Logarithmic ratio of two powers: 10·log10(P2/P1). +3 dB is about twice the power, +10 dB is ten times.
dBm|RF|Power relative to 1 mW: 10·log10(P / 1 mW). 0 dBm = 1 mW, 20 dBm = 100 mW, 30 dBm = 1 W.
dBi|RF|Antenna gain compared with an ideal isotropic radiator that sends equally in all directions.
dBd|RF|Antenna gain compared with a half-wave dipole. dBi = dBd + 2.15.
EIRP|RF|Equivalent Isotropically Radiated Power = Tx power + antenna gain − cable loss (dBm). The quantity regulators limit.
ERP|RF|Effective Radiated Power, referenced to a dipole: ERP = EIRP − 2.15 dB.
RSSI|Wi-Fi|Received Signal Strength Indicator: the receiver's estimate of incoming power, usually shown in dBm. Scale is vendor-specific.
SNR|RF|Signal-to-Noise Ratio in dB = signal (dBm) − noise floor (dBm). Higher SNR allows faster modulation.
SINR|RF|Signal to Interference-plus-Noise Ratio: SNR that also counts interference from other transmitters.
Noise floor|RF|Total unwanted RF energy at the receiver (thermal noise plus interference), typically −90 to −100 dBm on Wi-Fi.
Thermal noise|RF|Random noise from electron motion: N = −174 dBm/Hz + 10·log10(bandwidth in Hz) at 290 K.
Noise figure|RF|How much a receiver chain degrades the SNR, in dB. Lower is better.
Receiver sensitivity|RF|Weakest signal at which a receiver can still decode a given data rate.
Link budget|RF|Sum of all gains and losses between transmitter and receiver, used to predict received power.
Path loss|RF|Reduction of signal power as it travels through space and obstacles.
FSPL|RF|Free-space path loss: 20·log10(d km) + 20·log10(f MHz) + 32.44 dB.
Fade margin|RF|Extra signal above receiver sensitivity reserved for fading; typically 10-20 dB.
Multipath|RF|Signal reaching the receiver by several reflected paths; causes fading and inter-symbol interference.
Fresnel zone|RF|Ellipsoid around the line of sight; keep at least 60% of the first zone clear of obstacles.
Wavelength|RF|λ = c / f. About 12.5 cm at 2.4 GHz and 6 cm at 5 GHz.
Attenuation|RF|Signal loss in a medium: interior walls typically 3-15 dB, concrete and metal far more.
Shannon capacity|RF|C = B·log2(1 + SNR): theoretical maximum error-free data rate for bandwidth B.
EVM|RF|Error Vector Magnitude: how far received constellation points are from ideal. High-order QAM needs very low EVM.
VSWR|RF|Voltage Standing Wave Ratio: mismatch measure; 1:1 is perfect, below 2:1 is generally acceptable.
Return loss|RF|Reflected-power measure in dB: −20·log10 of the reflection coefficient. Higher is better.
Reflection coefficient|RF|Γ = (ZL − Z0)/(ZL + Z0): fraction of voltage reflected at an impedance mismatch.
Insertion loss|RF|Signal lost by adding a cable, connector or component into the path.
Channel width|Wi-Fi|Spectrum used by one channel (20/40/80/160/320 MHz). Wider is faster but noisier and leaves fewer channels.
Co-channel interference|Wi-Fi|Access points on the same channel share airtime and take turns transmitting (CSMA/CA).
Adjacent-channel interference|Wi-Fi|Partly overlapping channels corrupt each other's frames; usually worse than co-channel sharing.
Non-overlapping channels|Wi-Fi|On 2.4 GHz with 20 MHz width: channels 1, 6 and 11 (or 1, 5, 9, 13 where 13 is allowed).
DFS|Wi-Fi|Dynamic Frequency Selection: radar detection that forces APs off certain 5 GHz channels.
OFDM|Wi-Fi|Orthogonal Frequency Division Multiplexing: data is split across many closely spaced subcarriers.
OFDMA|Wi-Fi|Wi-Fi 6 multi-user OFDM: one transmission is shared by several clients using Resource Units.
Subcarrier|Wi-Fi|One narrow tone in OFDM: 312.5 kHz spacing in 11a/n/ac, 78.125 kHz in 11ax.
Resource Unit (RU)|Wi-Fi|Group of subcarriers assigned to one client in OFDMA.
QAM|Wi-Fi|Quadrature Amplitude Modulation: 64-QAM carries 6 bits per symbol, 256-QAM 8, 1024-QAM 10, 4096-QAM 12.
BPSK / QPSK|Wi-Fi|Basic phase modulations carrying 1 and 2 bits per symbol; robust, used at the weakest signal levels.
Coding rate|Wi-Fi|Useful share of transmitted bits (1/2, 2/3, 3/4, 5/6); the rest is error-correction overhead.
MCS|Wi-Fi|Modulation and Coding Scheme index: a preset pair of modulation and coding rate.
Guard interval|Wi-Fi|Pause between symbols that absorbs multipath echoes: 0.4/0.8 µs short, 1.6/3.2 µs long.
MIMO|Wi-Fi|Multiple-Input Multiple-Output: several antennas send and receive parallel spatial streams.
MU-MIMO|Wi-Fi|Multi-User MIMO: the AP serves several clients simultaneously on different spatial streams.
Spatial stream|Wi-Fi|One independent data stream in MIMO. Rate scales with the stream count (2×2 = 2 streams).
Beamforming|Wi-Fi|Adjusting phase and amplitude across antennas to focus energy toward a client.
PHY rate|Wi-Fi|Raw link speed negotiated by the radios; real throughput is roughly 50-70% of it.
Airtime|Wi-Fi|Wi-Fi is half-duplex and shared; slow clients use more airtime and slow everyone down.
SSID|Wi-Fi|Service Set Identifier: the human-readable network name.
BSSID|Wi-Fi|MAC address of one access-point radio; each band and SSID usually has its own.
BSS / ESS|Wi-Fi|BSS is one AP plus its clients; an ESS is several APs sharing an SSID so clients can roam.
Roaming (802.11k/v/r)|Wi-Fi|Standards that help clients move between APs quickly: neighbour reports, steering, fast transition.
BSS Coloring|Wi-Fi|Wi-Fi 6 tag that lets APs ignore weak same-channel neighbours and reuse spectrum.
TWT|Wi-Fi|Target Wake Time: Wi-Fi 6 scheduling so IoT and battery devices sleep between transmissions.
MLO|Wi-Fi|Multi-Link Operation (Wi-Fi 7): one client uses several bands at the same time.
Beacon|Wi-Fi|Frame an AP broadcasts about every 102.4 ms announcing its SSID and capabilities.
DTIM|Wi-Fi|Delivery Traffic Indication Message: tells sleeping clients when buffered broadcast data is waiting.
CSMA/CA|Wi-Fi|Carrier Sense Multiple Access with Collision Avoidance: listen before talking.
Hidden node|Wi-Fi|Two clients that cannot hear each other but both reach the AP, causing collisions.
RTS/CTS|Wi-Fi|Request/Clear-to-Send handshake that reduces hidden-node collisions.
WMM / QoS|Wi-Fi|Traffic classes (voice, video, best effort, background) that give time-sensitive data priority.
Omnidirectional antenna|Antenna|Radiates roughly equally in all horizontal directions; typical for router rod antennas.
Directional antenna|Antenna|Concentrates energy in one direction (yagi, patch, dish) for longer range.
Beamwidth|Antenna|Angle over which antenna gain stays within 3 dB of its peak.
Polarization|Antenna|Orientation of the radiated electric field (vertical, horizontal, circular). Mismatch costs signal.
Latency|Networking|Round-trip delay in milliseconds; under 5 ms to the router is typical on a good LAN.
Jitter|Networking|Variation in latency; hurts voice and video calls.
Packet loss|Networking|Percentage of packets that never arrive; above 1% is noticeable.
Throughput|Networking|Actual data delivered per second, after protocol overhead and retries.
Goodput|Networking|Application-level useful data rate, excluding headers and retransmissions.
MTU|Networking|Maximum Transmission Unit: largest packet size, normally 1500 bytes on Ethernet.
NAT|Networking|Network Address Translation: shares one public IP among many private devices.
DHCP|Networking|Automatically assigns IP address, gateway and DNS to clients for a lease period.
DNS|Networking|Translates names such as example.com into IP addresses.
ARP|Networking|Maps IPv4 addresses to MAC addresses on the local network.
MAC address|Networking|48-bit hardware address of a network interface, e.g. AA:BB:CC:DD:EE:FF.
OUI|Networking|First 3 bytes of a MAC address, identifying the manufacturer.
Locally administered MAC|Networking|MAC with the second-lowest bit of the first byte set; used for private/randomised addresses and virtual machines.
Subnet mask / CIDR|Networking|Defines network size: 255.255.255.0 = /24 = 254 usable hosts.
Default gateway|Networking|Router address that clients send non-local traffic to.
VLAN|Networking|Logical separation of one physical network into isolated segments (802.1Q).
UPnP|Networking|Lets devices open router ports automatically; convenient but a security risk if abused.
TR-069 (CWMP)|Networking|Protocol ISPs use to remotely configure and monitor routers (default port 7547).
Telnet|Security|Unencrypted remote console; should be disabled on routers in favour of SSH.
WPS|Security|Wi-Fi Protected Setup push-button/PIN pairing; the PIN mode is vulnerable and best disabled.
WPA2|Security|AES-CCMP encryption with a 4-way handshake; weak passphrases can be cracked offline.
WPA3|Security|Uses SAE (Dragonfly) for the password exchange, giving forward secrecy and protection against offline guessing.
PMF (802.11w)|Security|Protected Management Frames: stops spoofed deauthentication attacks; mandatory in WPA3.
802.1X / RADIUS|Security|Per-user enterprise authentication through a RADIUS server instead of a shared passphrase.
Evil twin|Security|Rogue AP copying a real SSID to trick clients into connecting.
Captive portal|Security|Login page shown before network access is granted, typical for guest Wi-Fi.
Voltage|Electrical|Electrical potential difference in volts (V).
Current|Electrical|Flow of charge in amperes (A).
Resistance|Electrical|Opposition to DC current in ohms: R = V / I.
Impedance|Electrical|Opposition to AC current, in ohms. RF systems use 50 Ω; Ethernet pairs are 100 Ω differential.
Ohm's law|Electrical|V = I × R.
Electrical power|Electrical|P = V × I = I²R = V²/R, in watts.
Energy (kWh)|Electrical|Power over time; 1 kWh = 1000 W for one hour. This is what the electricity bill charges for.
Power factor|Electrical|Ratio of real to apparent power (0-1); poor power factor wastes supply capacity.
Efficiency|Electrical|Output power ÷ input power; cheap power adapters are often only 70-85% efficient.
Voltage drop|Electrical|Voltage lost along a conductor (V = I × R); matters for long PoE or low-voltage runs.
Joule heating|Electrical|Power lost as heat in a conductor: P = I²R.
RMS|Electrical|Root mean square: the DC-equivalent value of an AC voltage or current.
SMPS|Electrical|Switched-mode power supply: compact, efficient AC/DC converter used in routers and chargers.
Ripple|Electrical|Residual AC variation on a DC supply; excess ripple adds noise to RF circuits.
Standby power|Electrical|Power drawn while idle; always-on network gear runs 24 h × 365 days.
UPS|Electrical|Uninterruptible Power Supply: battery backup that keeps routers and servers alive during outages.
Surge protector|Electrical|Clamps voltage spikes (MOVs) to protect equipment.
Grounding|Electrical|Low-resistance path to earth for safety and to drain static and surge energy.
PoE|Power|Power over Ethernet: DC power delivered on the data cable (802.3af/at/bt).
PSE / PD|Power|Power Sourcing Equipment (switch or injector) and Powered Device (AP, camera, phone).
Crosstalk (NEXT/FEXT)|Cabling|Unwanted coupling between cable pairs, measured at the near end (NEXT) or far end (FEXT).
Cat5e / Cat6 / Cat6a|Cabling|Twisted-pair categories rated 100 / 250 / 500 MHz; Cat6a carries 10 GbE to 100 m.
"""
GLOSSARY = sorted((tuple(l.split("|", 2)) for l in GLOSSARY_RAW.strip().splitlines()), key=lambda x: x[0].lower())


# --------------------------------------------------------------------------
# widgets
# --------------------------------------------------------------------------
class Card(tk.Frame):
    def __init__(self, master, title):
        super().__init__(master, bg=C["card"], padx=16, pady=12, highlightthickness=1, highlightbackground=C["line"])
        tk.Label(self, text=title.upper(), bg=C["card"], fg=C["muted"], font=(FONT, 9, "bold")).pack(anchor="w")
        self.val = tk.Label(self, text="-", bg=C["card"], fg=C["text"], font=(FONT, 20, "bold"))
        self.val.pack(anchor="w", pady=(4, 0))
        self.sub = tk.Label(self, text="", bg=C["card"], fg=C["muted"], font=(FONT, 9))
        self.sub.pack(anchor="w")

    def set(self, value, sub="", color=None):
        self.val.config(text=value, fg=color or C["text"])
        self.sub.config(text=sub)


class KVTable(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=("value",), show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Property", anchor="w")
        self.tree.heading("value", text="Value", anchor="w")
        self.tree.column("#0", width=300, stretch=False)
        self.tree.column("value", width=700)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("group", background=C["card"], foreground=C["accent"])
        for t, col in (("good", C["good"]), ("warn", C["warn"]), ("bad", C["bad"])):
            self.tree.tag_configure(t, foreground=col)
        self.tree.bind("<Control-c>", self.copy)
        self.tree.bind("<Double-1>", self.copy)

    def load(self, sections):
        self.tree.delete(*self.tree.get_children())
        for title, rows in sections.items():
            g = self.tree.insert("", "end", text=title, values=("",), open=(not title.startswith("Raw")), tags=("group",))
            for k, v in rows.items():
                v = str(v)
                tag = ()
                for lvl in ("GOOD", "WARN", "BAD"):
                    if v.startswith(f"[{lvl}]"):
                        tag = (lvl.lower(),)
                self.tree.insert(g, "end", text=str(k), values=(v,), tags=tag)

    def copy(self, _e=None):
        lines = [f"{self.tree.item(i, 'text')}: {self.tree.set(i, 'value')}" for i in self.tree.selection()]
        if lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))


def make_tree(master, cols):
    frame = ttk.Frame(master)
    ids = [f"c{i}" for i in range(len(cols))]
    tree = ttk.Treeview(frame, columns=ids, show="headings", selectmode="browse")
    for i, (h, w) in zip(ids, cols):
        tree.heading(i, text=h, anchor="w")
        tree.column(i, width=w, anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    for tag, col in (("me", C["accent"]), ("gw", C["good"]), ("priv", C["muted"]), ("total", C["warn"]),
                     ("bad", C["bad"]), ("warn", C["warn"]), ("good", C["good"])):
        tree.tag_configure(tag, foreground=col)
    return frame, tree


def sort_tree(tree, col, rev):
    def key(x):
        v = str(x[0]).replace(",", "")
        try:
            return (0, float(v))
        except ValueError:
            return (1, v.lower())
    items = sorted(((tree.set(k, col), k) for k in tree.get_children("")), key=key, reverse=rev)
    for i, (_, k) in enumerate(items):
        tree.move(k, "", i)
    tree.heading(col, command=lambda: sort_tree(tree, col, not rev))


class FieldForm(tk.Toplevel):
    """fields: (key, label, kind, options); kind = text | num | choice"""

    def __init__(self, app, title, fields, values, on_save):
        super().__init__(app)
        self.title(title)
        self.configure(bg=C["bg"])
        self.transient(app)
        self.grab_set()
        self.fields, self.on_save, self.vars = fields, on_save, {}
        body = ttk.Frame(self, padding=20)
        body.pack()
        for i, (key, label, kind, opts) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=i, column=0, sticky="w", pady=6, padx=(0, 14))
            var = tk.StringVar(value=str(values.get(key, "")))
            if kind == "choice":
                w = ttk.Combobox(body, textvariable=var, values=opts, state="readonly", width=34)
            else:
                w = ttk.Entry(body, textvariable=var, width=37)
            w.grid(row=i, column=1, pady=6)
            self.vars[key] = var
        bt = ttk.Frame(body)
        bt.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(bt, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(bt, text="Save", style="Accent.TButton", command=self.save).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())

    def save(self):
        out = {}
        try:
            for key, label, kind, opts in self.fields:
                v = self.vars[key].get().strip()
                out[key] = float(v) if kind == "num" and v else (0.0 if kind == "num" else v)
        except ValueError:
            messagebox.showerror(APP_NAME, "Please enter valid numbers.", parent=self)
            return
        self.on_save(out)
        self.destroy()


# --------------------------------------------------------------------------
# application
# --------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {VERSION}  -  Router & Network Intelligence Suite")
        self.geometry("1260x820")
        self.minsize(1040, 680)
        self.configure(bg=C["bg"])
        self.S = load_settings()
        self.q = queue.Queue()
        self.probe_sections, self.devices, self.nearby, self.wifi = {}, [], [], None
        self.cost_summary = {}
        self.build_style()
        self.build_header()
        self.status = tk.Label(self, text="Ready", bg=C["panel"], fg=C["muted"], font=(FONT, 9), anchor="w", padx=14, pady=6)
        self.status.pack(side="bottom", fill="x")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        names = ("Router", "Devices & LAN", "Wi-Fi Airspace", "Cost & TCO", "Calculators", "Reference", "Glossary")
        self.tabs = {n: ttk.Frame(self.nb, padding=14) for n in names}
        for n in names:
            self.nb.add(self.tabs[n], text=n)
        self.build_router()
        self.build_devices()
        self.build_air()
        self.build_cost()
        self.build_calc()
        self.build_ref()
        self.build_gloss()
        self.bind("<F5>", lambda e: self.scan_all())
        self.bind("<Control-e>", lambda e: self.export())
        self.pump()
        self.render_router()
        self.refresh_cost()
        self.after(400, self.scan_all)

    # ---- plumbing ----------------------------------------------------------
    def bg(self, fn, cb):
        def worker():
            try:
                res = fn()
            except Exception as e:  # noqa
                traceback.print_exc()
                res = e
            self.q.put((cb, res))
        threading.Thread(target=worker, daemon=True).start()

    def pump(self):
        try:
            while True:
                cb, res = self.q.get_nowait()
                try:
                    if isinstance(res, Exception):
                        self.status.config(text=f"Error: {res}")
                    else:
                        cb(res)
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def build_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["text"], font=(FONT, 10))
        s.configure("TFrame", background=C["bg"])
        s.configure("TLabel", background=C["bg"], foreground=C["text"])
        s.configure("Muted.TLabel", foreground=C["muted"])
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=C["panel"], foreground=C["muted"], padding=(16, 9),
                    font=(FONT, 10, "bold"), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", C["card"])], foreground=[("selected", C["accent"])])
        s.configure("Treeview", background=C["panel"], fieldbackground=C["panel"], foreground=C["text"], rowheight=28, borderwidth=0)
        s.configure("Treeview.Heading", background=C["card"], foreground=C["muted"], font=(FONT, 9, "bold"), relief="flat", padding=6)
        s.map("Treeview", background=[("selected", C["accent"])], foreground=[("selected", "#ffffff")])
        s.configure("TButton", background=C["card"], foreground=C["text"], padding=(14, 8), borderwidth=0, font=(FONT, 10, "bold"))
        s.map("TButton", background=[("active", C["line"])])
        s.configure("Accent.TButton", background=C["accent"], foreground="#ffffff")
        s.map("Accent.TButton", background=[("active", "#3c78ec")])
        s.configure("TEntry", fieldbackground=C["card"], foreground=C["text"], insertcolor=C["text"], bordercolor=C["line"], padding=5)
        s.configure("TCombobox", fieldbackground=C["card"], background=C["card"], foreground=C["text"], arrowcolor=C["text"], padding=5)
        s.map("TCombobox", fieldbackground=[("readonly", C["card"])], foreground=[("readonly", C["text"])])
        self.option_add("*TCombobox*Listbox.background", C["card"])
        self.option_add("*TCombobox*Listbox.foreground", C["text"])

    def build_header(self):
        h = tk.Frame(self, bg=C["bg"], padx=22, pady=14)
        h.pack(fill="x")
        left = tk.Frame(h, bg=C["bg"])
        left.pack(side="left")
        tk.Label(left, text=APP_NAME, bg=C["bg"], fg=C["text"], font=(FONT, 22, "bold")).pack(anchor="w")
        tk.Label(left, text="Router & Network Intelligence Suite  ·  F5 scan everything  ·  Ctrl+E export",
                 bg=C["bg"], fg=C["muted"], font=(FONT, 9)).pack(anchor="w")
        right = tk.Frame(h, bg=C["bg"])
        right.pack(side="right")
        ttk.Button(right, text="Scan everything", style="Accent.TButton", command=self.scan_all).pack(side="left", padx=4)
        ttk.Button(right, text="Export report…", command=self.export).pack(side="left", padx=4)

    def scan_all(self):
        self.run_probe()
        self.scan_devices()
        self.scan_air()

    # ---- Router ------------------------------------------------------------
    def build_router(self):
        f = self.tabs["Router"]
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="Probe router now", style="Accent.TButton", command=self.run_probe).pack(side="left")
        ttk.Button(bar, text="Edit router specs…", command=self.edit_router).pack(side="left", padx=8)
        ttk.Label(bar, text="Assumed noise floor (dBm):", style="Muted.TLabel").pack(side="left", padx=(18, 4))
        self.noise_var = tk.StringVar(value=str(self.S["noise_dbm"]))
        ttk.Entry(bar, textvariable=self.noise_var, width=6).pack(side="left")
        ttk.Label(bar, text="Double-click a row to copy it", style="Muted.TLabel").pack(side="right")
        self.router_tbl = KVTable(f)
        self.router_tbl.pack(fill="both", expand=True)

    def run_probe(self):
        self.status.config(text="Probing router (ping, ports, ARP, HTTP banner, DHCP, Wi-Fi)…")
        noise = fnum(self.noise_var.get(), -95)
        self.S["noise_dbm"] = noise
        self.bg(lambda: probe_router(self.S, noise), self.apply_probe)

    def apply_probe(self, res):
        self.probe_sections, self.wifi = res
        self.render_router()
        self.refresh_cost()
        self.status.config(text=f"Router probe finished {datetime.now():%H:%M:%S}")

    def render_router(self):
        view = {}
        ps = dict(self.probe_sections)
        findings = ps.pop("Findings", None)
        if findings:
            view["Findings"] = findings
        for k in ("Router identity", "Reachability", "Services on router", "Addressing & DHCP", "Wi-Fi radio (connected AP)"):
            if k in ps:
                view[k] = ps.pop(k)
        view["Router specification & cost (your entries)"] = router_spec_section(self.S)
        view.update(ps)
        self.router_view = view
        self.router_tbl.load(view)

    def edit_router(self):
        fields = [("model", "Model", "text", None), ("standard", "Wi-Fi standard", "choice", list(STD_PARAMS)),
                  ("width", "Channel width (MHz)", "choice", ["20", "40", "80", "160", "320"]),
                  ("streams", "Spatial streams", "choice", ["1", "2", "3", "4", "8"]),
                  ("tx_dbm", "Tx power per chain (dBm)", "num", None), ("ant_gain", "Antenna gain (dBi)", "num", None),
                  ("cable_loss", "Cable loss (dB)", "num", None), ("price", "Purchase price", "num", None),
                  ("watts", "Power draw (W)", "num", None), ("hours", "Hours per day", "num", None),
                  ("purchased", "Purchased (YYYY-MM-DD)", "text", None), ("notes", "Notes", "text", None)]

        def save(d):
            d["width"], d["streams"] = int(fnum(d["width"], 80)), int(fnum(d["streams"], 2))
            self.S["router"].update(d)
            save_settings(self.S)
            self.render_router()
            self.refresh_cost()
        FieldForm(self, "Router specifications", fields, self.S["router"], save)

    # ---- Devices -----------------------------------------------------------
    def build_devices(self):
        f = self.tabs["Devices & LAN"]
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="Scan LAN", style="Accent.TButton", command=self.scan_devices).pack(side="left")
        ttk.Button(bar, text="Edit device (watts, price…)", command=self.edit_device).pack(side="left", padx=8)
        ttk.Button(bar, text="Scan ports of selected", command=self.scan_ports).pack(side="left")
        ttk.Button(bar, text="Export CSV", command=self.export_devices).pack(side="right")
        self.dev_info = ttk.Label(f, text="", style="Muted.TLabel")
        self.dev_info.pack(anchor="w", pady=(0, 6))
        cols = [("IP", 105), ("Name", 150), ("MAC", 135), ("Vendor (approx.)", 140), ("Type", 120), ("OS guess (TTL)", 170),
                ("ms", 45), ("Watts", 55), ("h/day", 50), ("Price", 65), ("kWh/mo", 65), ("Cost/mo", 70)]
        frame, self.dev_tree = make_tree(f, cols)
        frame.pack(fill="both", expand=True)
        for i in range(len(cols)):
            self.dev_tree.heading(f"c{i}", command=lambda i=i: sort_tree(self.dev_tree, f"c{i}", False))
        self.dev_tree.bind("<Double-1>", lambda e: self.edit_device() if self.dev_tree.identify_region(e.x, e.y) == "cell" else None)
        self.dev_total = ttk.Label(f, text="", style="Muted.TLabel")
        self.dev_total.pack(anchor="w", pady=(8, 0))
        ttk.Label(f, style="Muted.TLabel", text="Blue = this computer · green = router · grey = private/randomised MAC. "
                  "Watts are type-based estimates until you edit them with real values.").pack(anchor="w")

    def eff(self, d):
        st = self.S["devices"].get(d["mac"], {})
        name = st.get("name") or d["host"] or ("This computer" if d["me"] else "-")
        typ = st.get("type") or d["type"]
        watts = st["watts"] if "watts" in st else TYPE_WATTS.get(typ, 10)
        hours = st.get("hours", 24.0)
        return name, typ, watts, hours, st.get("price", 0.0)

    def scan_devices(self):
        self.status.config(text="Sweeping the LAN (ping + ARP). This takes ~10-20 seconds…")
        self.bg(lambda: lan_scan(self.S["oui_extra"]), self.apply_devices)

    def apply_devices(self, res):
        self.devices, info = res
        self.dev_info.config(text=f"Subnet: {info}   ·   {len(self.devices)} devices found")
        self.render_devices()
        self.refresh_cost()
        self.status.config(text=f"LAN scan finished {datetime.now():%H:%M:%S}")

    def render_devices(self):
        t = self.dev_tree
        t.delete(*t.get_children())
        tw = tk_ = 0.0
        for d in self.devices:
            name, typ, watts, hours, price = self.eff(d)
            kwh = watts * hours * 30 / 1000
            cost = kwh * self.S["tariff"]
            tw += watts
            tk_ += cost
            tag = "me" if d["me"] else "gw" if d["gw"] else "priv" if "Locally" in d["kind"] else ""
            t.insert("", "end", iid=d["ip"], tags=(tag,) if tag else (), values=(
                d["ip"], name, d["mac"], d["vendor"], typ, d["os"][:32], "-" if d["ms"] is None else f"{d['ms']:.0f}",
                f"{watts:g}", f"{hours:g}", f"{price:,.0f}", f"{kwh:.1f}", f"{self.S['currency']}{cost:.2f}"))
        self.dev_total.config(text=f"Estimated draw of all listed devices: {tw:.0f} W  ·  "
                                   f"electricity ≈ {self.S['currency']}{tk_:,.2f} per month at {self.S['currency']}{self.S['tariff']}/kWh")

    def selected_device(self):
        sel = self.dev_tree.selection()
        if not sel:
            messagebox.showinfo(APP_NAME, "Select a device row first.")
            return None
        return next((d for d in self.devices if d["ip"] == sel[0]), None)

    def edit_device(self):
        d = self.selected_device()
        if not d or d["mac"] == "-":
            return
        name, typ, watts, hours, price = self.eff(d)
        vals = {"name": name if name != "-" else "", "type": typ, "watts": watts, "hours": hours,
                "price": price, "notes": self.S["devices"].get(d["mac"], {}).get("notes", "")}
        fields = [("name", "Device name", "text", None), ("type", "Type", "text", None), ("watts", "Power draw (W)", "num", None),
                  ("hours", "Hours per day", "num", None), ("price", "Purchase price", "num", None), ("notes", "Notes", "text", None)]

        def save(out):
            self.S["devices"][d["mac"]] = out
            save_settings(self.S)
            self.render_devices()
            self.refresh_cost()
        FieldForm(self, f"Edit {d['ip']}  ({d['mac']})", fields, vals, save)

    def scan_ports(self):
        d = self.selected_device()
        if not d:
            return
        if not messagebox.askokcancel(APP_NAME, f"Scan common TCP ports on {d['ip']}?\nOnly do this on devices you own or are authorised to test."):
            return
        self.status.config(text=f"Scanning ports on {d['ip']}…")

        def done(ports):
            txt = "\n".join(f"{p}  {PORTS_EXT[p]}" for p in ports) or "No common ports open."
            self.status.config(text="Port scan finished")
            messagebox.showinfo(APP_NAME, f"Open ports on {d['ip']}:\n\n{txt}")
        self.bg(lambda: port_scan(d["ip"], PORTS_EXT), done)

    def export_devices(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="devices", filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([self.dev_tree.heading(c)["text"] for c in self.dev_tree["columns"]])
                for k in self.dev_tree.get_children():
                    w.writerow(self.dev_tree.item(k, "values"))

    # ---- Wi-Fi airspace ----------------------------------------------------
    def build_air(self):
        f = self.tabs["Wi-Fi Airspace"]
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="Scan nearby networks", style="Accent.TButton", command=self.scan_air).pack(side="left")
        self.air_info = ttk.Label(bar, text="", style="Muted.TLabel")
        self.air_info.pack(side="left", padx=14)
        cols = [("Network (SSID)", 220), ("BSSID", 150), ("BSSID vendor", 120), ("Signal %", 70), ("≈ dBm", 60),
                ("Channel", 65), ("Band", 75), ("Security", 150)]
        frame, self.air_tree = make_tree(f, cols)
        frame.pack(fill="both", expand=True)
        for i in range(len(cols)):
            self.air_tree.heading(f"c{i}", command=lambda i=i: sort_tree(self.air_tree, f"c{i}", False))
        self.canv24 = tk.Canvas(f, bg=C["panel"], highlightthickness=0, height=150)
        self.canv24.pack(fill="x", pady=(10, 0))
        self.canv5 = tk.Canvas(f, bg=C["panel"], highlightthickness=0, height=150)
        self.canv5.pack(fill="x", pady=(8, 0))
        self.canv24.bind("<Configure>", lambda e: self.draw_air())

    def scan_air(self):
        self.status.config(text="Scanning nearby Wi-Fi…")
        self.bg(scan_nearby, self.apply_air)

    def apply_air(self, nets):
        self.nearby = nets
        t = self.air_tree
        t.delete(*t.get_children())
        for n in nets:
            tag = "good" if n["signal"] >= 65 else "warn" if n["signal"] >= 40 else ""
            t.insert("", "end", tags=(tag,) if tag else (), values=(
                n["ssid"], n["bssid"], mac_info(norm_mac(n["bssid"]), self.S["oui_extra"])[0], n["signal"],
                int(n["signal"] / 2 - 100), n["channel"] or "-", n["band"], n["security"]))
        if nets:
            b = best_channels(nets)
            self.air_info.config(text=f"{len(nets)} access points  ·  least-crowded: 2.4 GHz ch {b['2.4 GHz']}, 5 GHz ch {b['5 GHz']}")
        else:
            self.air_info.config(text="No networks found (Wi-Fi off, no adapter, or scanning unsupported).")
        self.draw_air()
        self.status.config(text="Wi-Fi scan finished")

    def draw_air(self):
        mine = self.wifi["channel"] if self.wifi else None
        for cv, chans, title in ((self.canv24, list(range(1, 14)), "2.4 GHz channel occupancy"),
                                 (self.canv5, [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165],
                                  "5 GHz channel occupancy")):
            cv.delete("all")
            w, h = max(cv.winfo_width(), 300), max(cv.winfo_height(), 100)
            cv.create_text(10, 10, text=title + "  (bar = strongest signal, number = networks)", fill=C["muted"], anchor="w", font=(FONT, 9, "bold"))
            slot = (w - 20) / len(chans)
            for i, c in enumerate(chans):
                on = [n for n in self.nearby if n["channel"] == c]
                x = 10 + i * slot
                if on:
                    bh = (h - 52) * max(n["signal"] for n in on) / 100
                    cv.create_rectangle(x + 3, h - 24 - bh, x + slot - 3, h - 24, width=0,
                                        fill=C["accent"] if c == mine else C["warn"] if len(on) > 1 else C["good"])
                    cv.create_text(x + slot / 2, h - 30 - bh, text=str(len(on)), fill=C["text"], font=(FONT, 8, "bold"))
                cv.create_text(x + slot / 2, h - 10, text=str(c), fill=C["accent"] if c == mine else C["muted"], font=(FONT, 8))

    # ---- Cost --------------------------------------------------------------
    def build_cost(self):
        f = self.tabs["Cost & TCO"]
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 12))
        self.v_tariff = tk.StringVar(value=str(self.S["tariff"]))
        self.v_cur = tk.StringVar(value=self.S["currency"])
        self.v_isp = tk.StringVar(value=str(self.S["isp_fee"]))
        self.v_years = tk.StringVar(value=str(self.S["years"]))
        for label, var, w in (("Electricity tariff / kWh", self.v_tariff, 8), ("Currency", self.v_cur, 5),
                              ("ISP fee / month", self.v_isp, 9), ("Years", self.v_years, 5)):
            ttk.Label(bar, text=label, style="Muted.TLabel").pack(side="left", padx=(0, 4))
            ttk.Entry(bar, textvariable=var, width=w).pack(side="left", padx=(0, 14))
        ttk.Button(bar, text="Recalculate", style="Accent.TButton", command=self.refresh_cost).pack(side="left")
        cards = ttk.Frame(f)
        cards.pack(fill="x")
        self.k = {}
        for i, n in enumerate(("Hardware (one-off)", "Electricity / month", "Running cost / month", "Total cost of ownership")):
            c = Card(cards, n)
            c.grid(row=0, column=i, sticky="nsew", padx=6)
            cards.columnconfigure(i, weight=1, uniform="k")
            self.k[n] = c
        cols = [("Item", 220), ("Type", 130), ("Price", 90), ("Watts", 70), ("h/day", 60), ("kWh/month", 90), ("Electricity/month", 120), ("Electricity/year", 110)]
        frame, self.cost_tree = make_tree(f, cols)
        frame.pack(fill="both", expand=True, pady=(14, 0))
        ttk.Label(f, style="Muted.TLabel", text="Router specs come from 'Edit router specs…'; device watts/prices from the Devices tab. "
                  "TCO = hardware + (electricity + ISP) × 12 × years. Estimated device wattages are marked until you edit them.").pack(anchor="w", pady=(8, 0))

    def refresh_cost(self):
        S = self.S
        S["tariff"], S["currency"] = fnum(self.v_tariff.get(), 0.12), self.v_cur.get() or "$"
        S["isp_fee"], S["years"] = fnum(self.v_isp.get()), max(fnum(self.v_years.get(), 3), 0.1)
        save_settings(S)
        cur = S["currency"]
        items = []
        r = S["router"]
        if r["price"] or r["model"]:
            items.append((r["model"] or "Router", "Router (gateway)", r["price"], r["watts"], r["hours"]))
        for d in self.devices:
            if d["gw"]:
                continue
            name, typ, watts, hours, price = self.eff(d)
            est = "" if "watts" in S["devices"].get(d["mac"], {}) else " (est.)"
            items.append((f"{name} [{d['ip']}]", typ + est, price, watts, hours))
        t = self.cost_tree
        t.delete(*t.get_children())
        hw = kwh_tot = 0.0
        for name, typ, price, watts, hours in items:
            kwh = watts * hours * 30 / 1000
            hw += price
            kwh_tot += kwh
            t.insert("", "end", values=(name, typ, f"{cur}{price:,.2f}", f"{watts:g}", f"{hours:g}", f"{kwh:.1f}",
                                        f"{cur}{kwh * S['tariff']:.2f}", f"{cur}{kwh * S['tariff'] * 12:.2f}"))
        elec = kwh_tot * S["tariff"]
        run_m = elec + S["isp_fee"]
        tco = hw + run_m * 12 * S["years"]
        t.insert("", "end", tags=("total",), values=("TOTAL", f"{len(items)} items", f"{cur}{hw:,.2f}", "", "",
                                                      f"{kwh_tot:.1f}", f"{cur}{elec:.2f}", f"{cur}{elec * 12:.2f}"))
        self.k["Hardware (one-off)"].set(f"{cur}{hw:,.0f}", f"{len(items)} items")
        self.k["Electricity / month"].set(f"{cur}{elec:,.2f}", f"{kwh_tot:.1f} kWh", C["warn"])
        self.k["Running cost / month"].set(f"{cur}{run_m:,.2f}", f"incl. ISP {cur}{S['isp_fee']:,.2f}", C["accent"])
        self.k["Total cost of ownership"].set(f"{cur}{tco:,.0f}", f"over {S['years']:g} years", C["good"])
        self.cost_summary = {"Hardware": f"{cur}{hw:,.2f}", "Electricity per month": f"{cur}{elec:,.2f}",
                             "ISP per month": f"{cur}{S['isp_fee']:,.2f}", f"TCO over {S['years']:g} years": f"{cur}{tco:,.2f}",
                             "Tariff": f"{cur}{S['tariff']}/kWh"}
        if self.devices:
            self.render_devices()

    # ---- Calculators -------------------------------------------------------
    def build_calc(self):
        f = self.tabs["Calculators"]
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        self.calc_list = tk.Listbox(f, bg=C["panel"], fg=C["text"], selectbackground=C["accent"], activestyle="none",
                                    bd=0, highlightthickness=0, font=(FONT, 10), width=30, exportselection=False)
        self.calc_list.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        for c in CALCS:
            self.calc_list.insert("end", "  " + c[0])
        self.calc_panel = ttk.Frame(f)
        self.calc_panel.grid(row=0, column=1, sticky="nsew")
        self.calc_list.bind("<<ListboxSelect>>", self.show_calc)
        self.calc_list.selection_set(0)
        self.show_calc()

    def show_calc(self, _e=None):
        sel = self.calc_list.curselection()
        if not sel:
            return
        name, desc, fields, fn = CALCS[sel[0]]
        for w in self.calc_panel.winfo_children():
            w.destroy()
        ttk.Label(self.calc_panel, text=name, font=(FONT, 15, "bold")).pack(anchor="w")
        ttk.Label(self.calc_panel, text=desc, style="Muted.TLabel", wraplength=720, justify="left").pack(anchor="w", pady=(4, 12))
        form = ttk.Frame(self.calc_panel)
        form.pack(anchor="w")
        vars_ = {}
        for i, fld in enumerate(fields):
            key, label, default = fld[:3]
            if key == "tariff":
                default = str(self.S["tariff"])
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 14))
            var = tk.StringVar(value=default)
            if len(fld) > 3:
                w = ttk.Combobox(form, textvariable=var, values=fld[3], state="readonly", width=28)
            else:
                w = ttk.Entry(form, textvariable=var, width=30)
                w.bind("<Return>", lambda e: go())
            w.grid(row=i, column=1, pady=4)
            vars_[key] = (var, len(fld) > 3)
        res = ttk.Treeview(self.calc_panel, columns=("v",), show="tree", height=8)
        res.column("#0", width=300)
        res.column("v", width=420)

        def go():
            vals = {}
            for k, (var, is_opt) in vars_.items():
                s = var.get().strip()
                if is_opt:
                    vals[k] = s
                else:
                    try:
                        vals[k] = float(s) if s else None
                    except ValueError:
                        messagebox.showerror(APP_NAME, f"'{s}' is not a number.")
                        return
            try:
                rows = fn(vals)
            except (ValueError, ZeroDivisionError, OverflowError, KeyError) as e:
                messagebox.showerror(APP_NAME, str(e) if str(e) and not isinstance(e, KeyError) else "Check the values you entered.")
                return
            res.delete(*res.get_children())
            for a, b in rows:
                res.insert("", "end", text=a, values=(b,))
        ttk.Button(self.calc_panel, text="Calculate", style="Accent.TButton", command=go).pack(anchor="w", pady=14)
        res.pack(anchor="w", fill="x")
        go()

    # ---- Reference ---------------------------------------------------------
    def build_ref(self):
        f = self.tabs["Reference"]
        self.refs = ref_tables()
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Table:", style="Muted.TLabel").pack(side="left")
        self.ref_var = tk.StringVar(value=list(self.refs)[0])
        cb = ttk.Combobox(bar, textvariable=self.ref_var, values=list(self.refs), state="readonly", width=30)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.show_ref())
        self.ref_holder = ttk.Frame(f)
        self.ref_holder.pack(fill="both", expand=True)
        self.ref_note = ttk.Label(f, text="", style="Muted.TLabel", wraplength=1100)
        self.ref_note.pack(anchor="w", pady=(8, 0))
        self.show_ref()

    def show_ref(self):
        for w in self.ref_holder.winfo_children():
            w.destroy()
        heads, rows, note = self.refs[self.ref_var.get()]
        width = max(90, 1100 // len(heads))
        frame, tree = make_tree(self.ref_holder, [(h, width) for h in heads])
        frame.pack(fill="both", expand=True)
        for r in rows:
            tree.insert("", "end", values=r)
        self.ref_note.config(text=note)

    # ---- Glossary ----------------------------------------------------------
    def build_gloss(self):
        f = self.tabs["Glossary"]
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Search:", style="Muted.TLabel").pack(side="left")
        self.g_search = tk.StringVar()
        ttk.Entry(bar, textvariable=self.g_search, width=28).pack(side="left", padx=8)
        cats = sorted({g[1] for g in GLOSSARY})
        self.g_cat = tk.StringVar(value="All")
        cb = ttk.Combobox(bar, textvariable=self.g_cat, values=["All"] + cats, state="readonly", width=14)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.render_gloss())
        self.g_count = ttk.Label(bar, text="", style="Muted.TLabel")
        self.g_count.pack(side="right")
        frame, self.g_tree = make_tree(f, [("Term", 210), ("Category", 100), ("Meaning", 850)])
        frame.pack(fill="both", expand=True)
        self.g_detail = tk.Label(f, text="", bg=C["card"], fg=C["text"], font=(FONT, 11), wraplength=1100,
                                 justify="left", anchor="w", padx=14, pady=12)
        self.g_detail.pack(fill="x", pady=(10, 0))
        self.g_tree.bind("<<TreeviewSelect>>", self.gloss_select)
        self.g_search.trace_add("write", lambda *a: self.render_gloss())
        self.render_gloss()

    def render_gloss(self):
        term, cat = self.g_search.get().strip().lower(), self.g_cat.get()
        t = self.g_tree
        t.delete(*t.get_children())
        n = 0
        for i, (a, b, c) in enumerate(GLOSSARY):
            if cat != "All" and b != cat:
                continue
            if term and term not in a.lower() and term not in c.lower():
                continue
            t.insert("", "end", iid=str(i), values=(a, b, c))
            n += 1
        self.g_count.config(text=f"{n} of {len(GLOSSARY)} terms")

    def gloss_select(self, _e=None):
        sel = self.g_tree.selection()
        if sel:
            a, b, c = GLOSSARY[int(sel[0])]
            self.g_detail.config(text=f"{a}  ({b})\n{c}")

    # ---- export ------------------------------------------------------------
    def build_report(self):
        r = {"Report": {"Tool": f"{APP_NAME} {VERSION}", "Generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Computer": socket.gethostname()}}
        r.update(getattr(self, "router_view", {}))
        if self.devices:
            r["Devices on LAN"] = {}
            for d in self.devices:
                name, typ, watts, hours, price = self.eff(d)
                r["Devices on LAN"][f"{d['ip']}  {name}"] = (
                    f"{d['mac']} | {d['vendor']} | {typ} | {watts:g} W x {hours:g} h | price {price:g} | {d['os']}")
        if self.nearby:
            r["Nearby networks"] = {f"{n['ssid']} [{n['bssid']}]": f"{n['signal']}% | ch {n['channel']} | {n['band']} | {n['security']}"
                                    for n in self.nearby}
        r["Cost summary"] = self.cost_summary
        return r

    def export(self):
        path = filedialog.asksaveasfilename(
            title="Export report", defaultextension=".txt", initialfile=f"wifi_dig_report_{datetime.now():%Y%m%d_%H%M}",
            filetypes=[("Text report", "*.txt"), ("JSON", "*.json"), ("CSV", "*.csv")])
        if not path:
            return
        rep = self.build_report()
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".json":
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(rep, f, indent=2, default=str)
            elif ext == ".csv":
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Section", "Property", "Value"])
                    for s, rows in rep.items():
                        for k, v in rows.items():
                            w.writerow([s, k, v])
            else:
                lines = [f"{APP_NAME} - Router & Network Report", "=" * 70]
                for s, rows in rep.items():
                    lines += ["", f"[{s}]"] + [f"  {k}: {v}" for k, v in rows.items()]
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            self.status.config(text=f"Exported to {path}")
            messagebox.showinfo(APP_NAME, f"Report saved:\n{path}")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not save report:\n{e}")


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    main()