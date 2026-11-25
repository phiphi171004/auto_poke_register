"""
Request Signing Module
Updated based on direct ARM64 assembly decompilation of libapp.so (Dart AOT)

Algorithms reconstructed from net_entry.dart:
1. initSDK (0x4b002c):
   raw_string = f"{appId}{source}{advChannel}{signing_value}"
   sign = MD5(raw_string)

2. register (0x5dcd60):
   raw_string = f"{appId}{userName}{password_md5}{source}{signing_value}"
   sign = MD5(raw_string)

3. login (0x5d8dc8):
   raw_string = f"{appId}{userName}{password_md5}{source}{signing_value}"
   sign = MD5(raw_string)

4. bindVisitor (0x547fb4):
   raw_string = f"{appId}{userId}{userName}{password_md5}{signing_value}"
   sign = MD5(raw_string)

5. bindZone (net_entry.dart:1978):
   raw_string = f"{userId}{appId}{gameZoneId}{source}{signing_value}"
   sign = MD5(raw_string)
"""

import hashlib
from datetime import datetime
from config import APP_CONFIG, PACKAGE_INFO, SIGNING_VALUE


class RequestSigner:
    """Sign requests according to game's exact Dart AOT algorithms"""

    SIGNING_VALUE = SIGNING_VALUE

    @staticmethod
    def generate_md5(input_string: str) -> str:
        """
        Exact implementation of generateMd5() from common_utils.dart (0x49411c)
        """
        utf8_bytes = input_string.encode('utf-8')
        md5_digest = hashlib.md5(utf8_bytes)
        return md5_digest.hexdigest().lower()

    @classmethod
    def hash_password(cls, plaintext_password: str) -> str:
        """
        Hash password for request body
        From net_entry.dart:4278
        password field = generateMd5(plaintext_password)
        """
        return cls.generate_md5(plaintext_password)

    @classmethod
    def sign_init_sdk(cls, app_id: str, source: str, adv_channel: str, signing_value: str = None) -> str:
        """
        From net_entry.dart:4b002c (initSDK):
        List_4: [appId, source, advChannel, signing_value]
        """
        s_val = signing_value if signing_value is not None else cls.SIGNING_VALUE
        raw = f"{app_id}{source}{adv_channel}{s_val}"
        return cls.generate_md5(raw)

    @classmethod
    def sign_register(cls, app_id: str, user_name: str, password_md5: str, source: str, signing_value: str = None) -> str:
        """
        From net_entry.dart:5dcd60 (register):
        List_5: [appId, userName, password_md5, source, signing_value]
        """
        s_val = signing_value if signing_value is not None else cls.SIGNING_VALUE
        raw = f"{app_id}{user_name}{password_md5}{source}{s_val}"
        return cls.generate_md5(raw)

    @classmethod
    def sign_login(cls, app_id: str, user_name: str, password_md5: str, source: str, signing_value: str = None) -> str:
        """
        From net_entry.dart:5d8dc8 (login):
        List_5: [appId, userName, password_md5, source, signing_value]
        """
        s_val = signing_value if signing_value is not None else cls.SIGNING_VALUE
        raw = f"{app_id}{user_name}{password_md5}{source}{s_val}"
        return cls.generate_md5(raw)

    @classmethod
    def sign_bind_visitor(cls, app_id: str, user_id: str, user_name: str, password_md5: str, signing_value: str = None) -> str:
        """
        From net_entry.dart:3140-3220 (bindVisitor, 0x547fb4):
        Formula: MD5(appId + userId + userName + password_md5 + signing_value)
        """
        s_val = signing_value if signing_value is not None else cls.SIGNING_VALUE
        raw = f"{app_id}{user_id}{user_name}{password_md5}{s_val}"
        return cls.generate_md5(raw)

    @classmethod
    def sign_bind_zone(cls, user_id: str, app_id: str, game_zone_id: str, source: str, signing_value: str = None) -> str:
        """
        From net_entry.dart:1978 (bindZone):
        List_5: [userId, appId, gameZoneId, source, signing_value]
        """
        s_val = signing_value if signing_value is not None else cls.SIGNING_VALUE
        raw = f"{user_id}{app_id}{game_zone_id}{source}{s_val}"
        return cls.generate_md5(raw)

    @staticmethod
    def get_client_time() -> str:
        """Dart DateTime.toString() format"""
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S.%f")

    @classmethod
    def build_init_sdk_body(
        cls,
        device_info: dict,
        first_install: bool = False,
        signing_value: str = None
    ) -> dict:
        """
        Build initSDK request body
        From NetRequest.initSdk() in net_entry.dart:2120-2281
        """
        app_id = str(APP_CONFIG["app_id"])
        source = str(APP_CONFIG["source"])
        adv_channel = str(APP_CONFIG["adv_channel"])

        body = {
            "appId": app_id,
            "advChannel": adv_channel,
            "firstInstall": 1 if first_install else 0,
            "model": device_info.get("model", ""),
            "operatorOs": device_info.get("operatorOs", ""),
            "device": device_info.get("device", ""),
            "deviceNo": device_info.get("deviceNo", ""),
            "source": APP_CONFIG["source"],
            "clientTime": cls.get_client_time(),
            "version": device_info.get("version", PACKAGE_INFO["version_name"]),
            "sdkVersion": APP_CONFIG["sdk_version"]
        }

        # Sign using exact formula
        body["sign"] = cls.sign_init_sdk(app_id, source, adv_channel, signing_value)
        return body

    @classmethod
    def build_register_body(
        cls,
        username: str,
        plaintext_password: str,
        device_info: dict,
        email: str = "",
        third_party_id: str = "",
        account_type: int = 0,
        ex_info: str = "",
        signing_value: str = None
    ) -> dict:
        """
        Build complete registration request body
        From NetRequest.register() in net_entry.dart:4112-4479
        """
        app_id = str(APP_CONFIG["app_id"])
        source = str(APP_CONFIG["source"])
        pwd_md5 = cls.hash_password(plaintext_password)

        body = {
            "appId": app_id,
            "userName": username,
            "password": pwd_md5,
            "email": email,
            "thirdPartyId": third_party_id,
            "accountType": account_type,
            "userChannel": APP_CONFIG["user_channel"],
            "advChannel": APP_CONFIG["adv_channel"],
            "exInfo": ex_info,
            "model": device_info.get("model", ""),
            "operatorOs": device_info.get("operatorOs", ""),
            "device": device_info.get("device", ""),
            "deviceNo": device_info.get("deviceNo", ""),
            "source": APP_CONFIG["source"],
            "clientTime": cls.get_client_time(),
            "version": device_info.get("version", PACKAGE_INFO["version_name"]),
            "sdkVersion": APP_CONFIG["sdk_version"]
        }

        # Calculate sign using correct assembly formula:
        body["sign"] = cls.sign_register(app_id, username, pwd_md5, source, signing_value)
        return body

    @classmethod
    def build_visitor_register_body(
        cls,
        device_info: dict,
        signing_value: str = None
    ) -> dict:
        """
        Build visitor registration body (userName is empty, random 8-char password)
        """
        import random, string
        chars = string.ascii_letters + string.digits
        random_password = ''.join(random.choices(chars, k=8))

        body = cls.build_register_body(
            username="",
            plaintext_password=random_password,
            device_info=device_info,
            signing_value=signing_value
        )
        body["_plaintext_password"] = random_password
        return body

    @classmethod
    def build_bind_visitor_body(
        cls,
        user_id: str,
        username: str,
        plaintext_password: str,
        device_info: dict,
        email: str = "",
        signing_value: str = None
    ) -> dict:
        """
        Build bindVisitor request body
        From NetRequest.bindVisitor() in net_entry.dart:3045-3232
        Formula: MD5(appId + userId + userName + password_md5 + signing_value)
        """
        app_id = str(APP_CONFIG["app_id"])
        pwd_md5 = cls.hash_password(plaintext_password)

        body = {
            "appId": app_id,
            "userId": str(user_id),
            "userName": username,
            "password": pwd_md5,
            "email": email,
            "model": device_info.get("model", ""),
            "operatorOs": device_info.get("operatorOs", ""),
            "device": device_info.get("device", ""),
            "deviceNo": device_info.get("deviceNo", ""),
            "source": APP_CONFIG["source"],
            "clientTime": cls.get_client_time(),
            "version": device_info.get("version", PACKAGE_INFO["version_name"]),
            "sdkVersion": APP_CONFIG["sdk_version"],
            "sign": cls.sign_bind_visitor(app_id, str(user_id), username, pwd_md5, signing_value)
        }
        return body

    @classmethod
    def build_login_body(
        cls,
        username: str,
        plaintext_password: str,
        device_info: dict,
        signing_value: str = None
    ) -> dict:
        """
        Build login request body
        From NetRequest.login() in net_entry.dart:3662-3980
        """
        app_id = str(APP_CONFIG["app_id"])
        source = str(APP_CONFIG["source"])
        pwd_md5 = cls.hash_password(plaintext_password)

        body = {
            "appId": app_id,
            "userName": username,
            "password": pwd_md5,
            "userChannel": APP_CONFIG["user_channel"],
            "advChannel": APP_CONFIG["adv_channel"],
            "model": device_info.get("model", ""),
            "operatorOs": device_info.get("operatorOs", ""),
            "device": device_info.get("device", ""),
            "deviceNo": device_info.get("deviceNo", ""),
            "source": APP_CONFIG["source"],
            "clientTime": cls.get_client_time(),
            "version": device_info.get("version", PACKAGE_INFO["version_name"]),
            "sdkVersion": APP_CONFIG["sdk_version"],
            "sign": cls.sign_login(app_id, username, pwd_md5, source, signing_value)
        }
        return body

    @classmethod
    def build_bind_zone_body(
        cls,
        user_id: str,
        game_zone_id: str,
        create_role: bool = True,
        signing_value: str = None
    ) -> dict:
        """
        Build bindZone request body
        From NetRequest.bindZone() in net_entry.dart:1978
        Formula: MD5(userId + appId + gameZoneId + source + signing_value)
        """
        app_id = str(APP_CONFIG["app_id"])
        source = str(APP_CONFIG["source"])
        u_id = str(user_id)
        zone_id = str(game_zone_id)

        sign = cls.sign_bind_zone(u_id, app_id, zone_id, source, signing_value)

        return {
            "appId": app_id,
            "userId": u_id,
            "gameZoneId": zone_id,
            "source": APP_CONFIG["source"],
            "createRole": 1 if create_role else 0,
            "advChannel": str(APP_CONFIG["adv_channel"]),
            "sign": sign
        }
