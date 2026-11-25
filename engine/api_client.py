"""
API Client for Pokemon Game
Handles all HTTP communication with game servers
"""

import requests
import time
import logging
from typing import Dict, Optional, Tuple
from config import (
    API_BASE_URL, ENDPOINTS, DEFAULT_HEADERS,
    RETRY_CONFIG, RATE_LIMIT
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.requests = []
    
    def wait_if_needed(self):
        """Wait if rate limit is reached"""
        now = time.time()
        
        # Remove old requests (>60s)
        self.requests = [t for t in self.requests if now - t < 60]
        
        # Check if we need to wait
        if len(self.requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.requests[0])
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                self.requests = []
        
        self.requests.append(now)


class APIClient:
    """Client for game API"""
    
    def __init__(self, max_per_minute: Optional[int] = None, proxy: Optional[Dict] = None):
        self.proxy = proxy
        self.max_per_minute = max_per_minute
        self.session = None
        self._init_session(use_proxy=True)
        rpm = max_per_minute if (max_per_minute is not None and max_per_minute > 0) else RATE_LIMIT["max_per_minute"]
        self.rate_limiter = RateLimiter(rpm)
        self.base_url = API_BASE_URL
        
        # Init SDK state
        self.init_data = None
        self.is_initialized = False

    def _init_session(self, use_proxy: bool = True):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if use_proxy and self.proxy and self.proxy.get("url"):
            self.session.proxies = {
                "http": self.proxy["url"],
                "https": self.proxy["url"]
            }
        
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        retry: bool = True
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Make HTTP request with retry logic
        
        Returns:
            (success, response_data, error_message)
        """
        url = self.base_url + endpoint
        
        # Rate limiting
        self.rate_limiter.wait_if_needed()
        
        retries = RETRY_CONFIG["max_retries"] if retry else 1
        last_error = None
        
        for attempt in range(retries):
            try:
                logger.debug(f"Request to {endpoint} (attempt {attempt + 1}/{retries})")

                # If proxy is configured, never fall back to direct connection to prevent IP leaks and WAF rate-limiting
                # if attempt == retries - 1 and self.proxy and self.session.proxies:
                #     logger.warning("   ⚠️ Proxy có vẻ không phản hồi tốt...")
                
                if method.upper() == "POST":
                    response = self.session.post(url, data=data, timeout=20)
                else:
                    response = self.session.get(url, params=data, timeout=20)
                
                # Log response
                logger.debug(f"Status: {response.status_code}")
                logger.debug(f"Response: {response.text[:500]}")
                
                # Check status code
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        
                        # Check if response indicates success
                        if self._is_success_response(json_data):
                            return True, json_data, None
                        else:
                            error_msg = self._extract_error_message(json_data)
                            return False, json_data, error_msg
                            
                    except ValueError:
                        return False, None, "Invalid JSON response"
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    
            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                logger.warning(f"⚠️ Hết thời gian chờ phản hồi (Timeout) lần thử {attempt + 1}")
                self._init_session()
                
            except requests.exceptions.ConnectionError as ce:
                last_error = "Connection error"
                err_text = str(ce)
                if "10061" in err_text or "refused" in err_text.lower():
                    logger.warning(f"⚠️ Cổng Proxy {self.proxy.get('host') if self.proxy else ''}:{self.proxy.get('port') if self.proxy else ''} bị đóng hoặc từ chối kết nối ([WinError 10061]). Bỏ qua cổng proxy này.")
                    self._init_session()
                elif "ProxyError" in err_text:
                    logger.warning(f"⚠️ Lỗi kết nối Proxy lần thử {attempt + 1}: {err_text[:120]}")
                    self._init_session()
                else:
                    logger.warning(f"⚠️ Lỗi kết nối mạng (Connection error) lần thử {attempt + 1}")
                    self._init_session()
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"⚠️ Lỗi bất ngờ: {e}")
                self._init_session()
            
            # Wait before retry with progressive backoff
            if attempt < retries - 1:
                wait_time = 2.0 * (attempt + 1)
                time.sleep(wait_time)
        
        return False, None, last_error
    
    def _is_success_response(self, data: Dict) -> bool:
        """
        Check if response indicates success
        Different endpoints may have different success indicators
        """
        # Common success indicators based on analysis
        if isinstance(data, dict):
            # Check for explicit success field
            if data.get("status") == "success":
                return True
            if data.get("code") == 0 or data.get("code") == "0" or data.get("code") == 200 or data.get("code") == "200":
                return True
            if data.get("success") is True:
                return True
            
            # Check for data field (usually means success)
            if "data" in data and data.get("code") != -1:
                return True
        
        return False
    
    def _extract_error_message(self, data: Dict) -> str:
        """Extract error message from response with user-friendly translation"""
        if isinstance(data, dict):
            code = data.get("code")
            # Try various error fields
            for field in ["error_msg", "error_message", "message", "msg", "error", "errorMsg", "desc"]:
                if field in data and data[field]:
                    msg = str(data[field])
                    if code == 108 or "user has bind" in msg.lower():
                        return f"Tài khoản đã tồn tại trên máy chủ (Error 108: {msg})"
                    if code and code != 0 and code != 200:
                        return f"{msg} (Mã lỗi: {code})"
                    return msg
            
            # Check for code-based errors
            if code and code != 0 and code != 200:
                if code == 108:
                    return "Tài khoản đã tồn tại trên máy chủ (Error 108: user has bind the account)"
                return f"Error code: {code}"
        
        return "Unknown error"
    
    # API Methods
    
    def init_sdk(self, init_body: Dict) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Initialize SDK - MUST be called before register
        
        From COMPLETE_VISITOR_FLOW_ANALYSIS.md:
        - App always calls initSDK() first
        - Response contains InitModelEntity with config
        - Required before any other API calls
        """
        logger.info("Calling initSDK...")
        success, data, error = self._request("POST", ENDPOINTS["init_sdk"], init_body)
        
        if success and data:
            # Store init response for future use
            self.init_data = data
            self.is_initialized = True
            logger.info("✅ SDK initialized successfully")
        else:
            logger.error(f"❌ initSDK failed: {error}")
        
        return success, data, error
    
    def register(
        self, 
        request_body: dict
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Register new account
        request_body should already be complete with all fields and sign
        """
        logger.info(f"Registering account: {request_body.get('userName', 'unknown')}")
        
        return self._request("POST", ENDPOINTS["register"], request_body)
    
    def login(
        self,
        request_body: Dict
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Login to existing account with built login body"""
        account = request_body.get("userName", "")
        logger.info(f"Logging in: {account}")
        return self._request("POST", ENDPOINTS["login"], request_body)
    
    def bind_visitor(
        self,
        request_body: Dict
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Bind visitor account to normal username/password (/client/user/bindVisitor/v5.0)"""
        user_id = request_body.get("userId", "unknown")
        user_name = request_body.get("userName", "unknown")
        logger.info(f"Upgrading visitor {user_id} to {user_name}...")
        return self._request("POST", ENDPOINTS["bind_visitor"], request_body)

    def bind_zone(
        self,
        request_body: Dict
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Bind to game zone/server"""
        zone_id = request_body.get("gameZoneId", "unknown")
        user_id = request_body.get("userId", "unknown")
        logger.info(f"Binding user {user_id} to zone: {zone_id}")
        return self._request("POST", ENDPOINTS["bind_zone"], request_body)
    
    def verify_user_info(
        self,
        user_token: str,
        device_info: Dict
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Verify user information"""
        logger.info("Verifying user info...")
        
        data = {
            "token": user_token,
            **device_info
        }
        
        return self._request("POST", ENDPOINTS["verify_user"], data)


if __name__ == "__main__":
    # Test API client
    logging.basicConfig(level=logging.DEBUG)
    
    client = APIClient()
    
    # Test with dummy data
    test_device = {
        "deviceNo": "TEST123",
        "manufacturer": "samsung",
        "model": "SM-G998B"
    }
    
    print("Testing API client...")
    print("Note: Requests will likely fail without proper signature")
    
    # Test init SDK
    success, data, error = client.init_sdk(test_device)
    print(f"\nInit SDK: {'✅' if success else '❌'}")
    if error:
        print(f"Error: {error}")
