"""
Device Fingerprint Generator
Based on analysis: device_infos.dart and device fingerprinting requirements
Version: 73.0.0 (Reverse Engineered from libapp.so ARM64 & device_infos.dart)
"""

import uuid
import random
import secrets
import hashlib
from datetime import datetime
from config import DEVICE_MODELS, SCREEN_RESOLUTIONS, PACKAGE_INFO


def generate_dynamic_wifi_ssid() -> str:
    """Generate realistic, diverse Wi-Fi SSIDs matching real Vietnamese user networks"""
    # 10% chance Android returns <unknown ssid> (standard when ACCESS_FINE_LOCATION is restricted)
    if random.random() < 0.10:
        return "<unknown ssid>"

    cat = random.choice(["viettel", "fpt", "vnpt", "home", "cafe", "router"])
    if cat == "viettel":
        return random.choice([
            f"Viettel_5G_{secrets.token_hex(2).upper()}",
            f"Viettel_{random.randint(100, 9999)}",
            f"Viettel_Home_{random.randint(10, 99)}",
            f"VT_{secrets.token_hex(2).upper()}_5G",
            "Viettel_WiFi",
            "Viettel_5G"
        ])
    elif cat == "fpt":
        return random.choice([
            f"FPT_Telecom_{random.randint(100, 9999)}",
            f"FPT_{secrets.token_hex(2).upper()}",
            f"FPT_5G_{random.randint(10, 99)}",
            "FPT_WiFi",
            "FPT_Home_WiFi"
        ])
    elif cat == "vnpt":
        return random.choice([
            f"VNPT_Home_{random.randint(100, 9999)}",
            f"VNPT_5G_{random.randint(10, 99)}",
            f"VNPT_{secrets.token_hex(2).upper()}",
            "VNPT_WiFi"
        ])
    elif cat == "cafe":
        return random.choice([
            f"Highlands_Coffee_Free_{random.randint(1, 20)}",
            f"The_Coffee_House_{random.randint(1, 30)}",
            f"PhucLong_Tea_{random.randint(1, 15)}",
            f"TraSua_Free_{random.randint(1, 50)}",
            f"Cafe_Pho_{random.randint(1, 99)}"
        ])
    elif cat == "home":
        return random.choice([
            f"Nha_Tro_T{random.randint(1, 5)}",
            f"Phong_{random.randint(101, 505)}",
            f"Family_WiFi_{random.randint(1, 9)}",
            f"Home_WiFi_5G_{secrets.token_hex(1).upper()}",
            f"My_WiFi_{random.randint(1, 99)}"
        ])
    else:
        return random.choice([
            f"TP-Link_{secrets.token_hex(2).upper()}",
            f"Tenda_{secrets.token_hex(2).upper()}",
            f"ASUS_Gaming_{secrets.token_hex(2).upper()}",
            f"Totolink_{secrets.token_hex(2).upper()}"
        ])


def generate_dynamic_mac() -> str:
    """Generate realistic randomized Wi-Fi MAC address (Android 10+ locally administered unicast)"""
    first_byte = random.choice([0x02, 0x06, 0x0A, 0x0E, 0x12, 0x16, 0x1A, 0x1E, 0x22, 0x26, 0x2A, 0x2E])
    remaining = [random.randint(0, 255) for _ in range(5)]
    return f"{first_byte:02x}:{remaining[0]:02x}:{remaining[1]:02x}:{remaining[2]:02x}:{remaining[3]:02x}:{remaining[4]:02x}"


class DeviceFingerprint:
    """Generate realistic device fingerprint matching real Android game client 100%"""
    
    def __init__(self):
        # Random device from 30+ modern pool
        device = random.choice(DEVICE_MODELS)
        screen = random.choice(SCREEN_RESOLUTIONS)
        
        # Basic device info
        self.manufacturer = device["manufacturer"]
        self.brand = device["brand"]
        self.model = device["model"]
        self.device_name = device["name"]
        self.sdk_version = device["sdk_version"]
        self.os_version = device["os_version"]
        
        # Screen info
        self.screen_width = screen["width"]
        self.screen_height = screen["height"]
        
        # Unique identifiers:
        # 1. Android ID: exactly 16-character lowercase hex without hyphens
        self.device_id = secrets.token_hex(8).lower()
        # 2. GAID (Google Advertising ID)
        self.advertising_id = str(uuid.uuid4()).lower()
        # 3. Adjust ADID (deviceNo): 32-character lowercase hex
        self.device_no = secrets.token_hex(16).lower()
        # 4. Hardware serial number
        self.serial_number = self._generate_serial()
        # 5. MAC Address (Android randomized MAC)
        self.mac_address = generate_dynamic_mac()
        
        # Simulated Network & Wi-Fi
        self.wifi_ssid = generate_dynamic_wifi_ssid()
        self.local_ip = self._generate_local_ip()
        
        # Network/Locale
        self.language = "vi-VN"
        self.country = "VN"
        
        # Flags
        self.is_physical_device = True
        
    def _generate_local_ip(self) -> str:
        """Generate realistic local network IP address"""
        subnet = random.choice(["192.168.1", "192.168.0", "192.168.2", "172.20.10", "10.0.0"])
        host = random.randint(3, 240)
        return f"{subnet}.{host}"
    
    def _generate_serial(self) -> str:
        """Generate hardware serial number"""
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return ''.join(random.choices(chars, k=8))
    
    def get_operator_os(self) -> str:
        """
        Get Android OS info in format expected by server:
        Android{os_version}#{wifi_name}#{local_ip}
        Directly reverse engineered from device_infos.dart:170-202:
        _StringBase::_interpolate([ 'Android', release, '#', wifiName, '#', wifiIP ])
        """
        return f"Android{self.os_version}#{self.wifi_ssid}#{self.local_ip}"
    
    def get_network_state(self) -> str:
        """Get network state"""
        return random.choice(["wifi", "wifi", "wifi", "4g", "5g"])
    
    def to_dict(self):
        """Export as dictionary"""
        return {
            "manufacturer": self.manufacturer,
            "brand": self.brand,
            "model": self.model,
            "deviceName": self.device_name,
            "sdkVersion": self.sdk_version,
            "osVersion": self.os_version,
            "screenWidth": self.screen_width,
            "screenHeight": self.screen_height,
            "advertisingId": self.advertising_id,
            "device": self.device_id,
            "deviceNo": self.device_no,
            "serialNumber": self.serial_number,
            "mac": self.mac_address,
            "wifiSsid": self.wifi_ssid,
            "localIp": self.local_ip,
            "language": self.language,
            "country": self.country,
            "isPhysicalDevice": self.is_physical_device,
            "idfv": self.device_id,
        }
    
    def to_api_dict(self):
        """
        Export as dictionary for API requests
        Matches format expected by _insertDeviceMsg() in net_entry.dart
        """
        return {
            "model": self.model,
            "operatorOs": self.get_operator_os(),
            "device": self.device_id,      # 16-hex Android ID
            "deviceNo": self.device_no,    # 32-hex Adjust ID
            "mac": self.mac_address,       # Realistic MAC address
            "osVersion": self.os_version,  # Android OS version (13, 14...)
            "source": 2,                   # Constant
            "clientTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": PACKAGE_INFO.get("version_name", "73.0.0"),  # App version 73.0.0
            "sdkVersion": "flt_250217",    # SDK version
            "network": self.get_network_state(),
        }
    
    def __repr__(self):
        return f"<Device {self.model} - {self.device_id}>"


def generate_multiple_devices(count):
    """Generate multiple unique devices"""
    devices = []
    used_ids = set()
    
    for _ in range(count):
        while True:
            device = DeviceFingerprint()
            if device.device_id not in used_ids:
                used_ids.add(device.device_id)
                devices.append(device)
                break
    
    return devices


if __name__ == "__main__":
    # Test
    device = DeviceFingerprint()
    print("Generated Device:")
    print(f"  Model: {device.model}")
    print(f"  Device (Android ID 16-hex): {device.device_id}")
    print(f"  Device No (32-hex): {device.device_no}")
    print(f"  MAC: {device.mac_address}")
    print(f"  WiFi SSID: {device.wifi_ssid}")
    print(f"  Operator OS: {device.get_operator_os()}")
    print(f"  Screen: {device.screen_width}x{device.screen_height}")
    print(f"  Version: {PACKAGE_INFO.get('version_name')}")
