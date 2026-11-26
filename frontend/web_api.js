// ========================================================
// POKEMON MASTER AUTO WEB - HTTP + WEBSOCKET BRIDGE
// Drop-in replacement for Electron's preload window.electronAPI
// ========================================================

(function () {
  'use strict';

  const SESSION_PIN_KEY = 'pokemon_web_access_pin';
  const WS_BASE_DELAY_MS = 1000;
  const WS_MAX_DELAY_MS = 15000;

  // Event listeners registry
  const listeners = {
    'log-message': [],
    'task-finished': [],
    'account-added': [],
    'servers-updated': [],
    'task-status': []
  };

  // Runtime state
  let configStatus = {
    storage: 'sqlite',
    running: false,
    pin_required: false
  };
  let ws = null;
  let wsReconnectTimer = null;
  let wsHeartbeatTimer = null;
  let wsReconnectDelay = WS_BASE_DELAY_MS;
  let wsShouldReconnect = true;
  let isAuthModalOpen = false;
  let readyResolved = false;
  let resolveReadyFn = null;

  const readyPromise = new Promise((resolve) => {
    resolveReadyFn = resolve;
  });

  function markReady() {
    if (!readyResolved && resolveReadyFn) {
      readyResolved = true;
      resolveReadyFn(configStatus);
    }
  }

  // Safe sessionStorage helpers
  function getStoredPin() {
    try {
      return sessionStorage.getItem(SESSION_PIN_KEY) || '';
    } catch (_err) {
      return '';
    }
  }

  function setStoredPin(pin) {
    try {
      if (pin) {
        sessionStorage.setItem(SESSION_PIN_KEY, pin);
      } else {
        sessionStorage.removeItem(SESSION_PIN_KEY);
      }
    } catch (_err) {
      // Ignore storage quota / privacy mode errors
    }
  }

  function notifyToast(message, icon = 'ℹ️') {
    if (typeof window.showWebToast === 'function') {
      window.showWebToast(message, icon);
      return;
    }
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    const iconSpan = document.createElement('span');
    iconSpan.textContent = icon;
    const msgSpan = document.createElement('span');
    msgSpan.textContent = message;
    toast.appendChild(iconSpan);
    toast.appendChild(msgSpan);
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 2600);
  }

  function emitEvent(eventName, data) {
    const callbacks = listeners[eventName];
    if (!Array.isArray(callbacks)) return;
    for (const cb of callbacks) {
      try {
        cb(data);
      } catch (err) {
        console.error(`[WebAPI] Listener error for "${eventName}":`, err);
      }
    }
  }

  // ================= Header Status Badges =================
  function updateWsBadge(state, detailText = '') {
    const badge = document.getElementById('ws-status-badge');
    const textEl = document.getElementById('ws-status-text');
    if (!badge) return;

    badge.classList.remove('status-online', 'status-connecting', 'status-offline');
    if (state === 'online') {
      badge.classList.add('status-online');
      if (textEl) textEl.textContent = detailText || 'WS Trực tuyến';
      badge.title = 'Kết nối WebSocket thời gian thực đang hoạt động';
    } else if (state === 'connecting') {
      badge.classList.add('status-connecting');
      if (textEl) textEl.textContent = detailText || 'Đang kết nối...';
      badge.title = 'Đang thiết lập kết nối WebSocket với máy chủ';
    } else {
      badge.classList.add('status-offline');
      if (textEl) textEl.textContent = detailText || 'Mất kết nối';
      badge.title = 'WebSocket bị ngắt, hệ thống đang tự động kết nối lại';
    }
  }

  function updateStorageBadge(storageMode) {
    const badge = document.getElementById('storage-status-badge');
    const textEl = document.getElementById('storage-status-text');
    if (!badge) return;

    const normalized = String(storageMode || 'sqlite').toLowerCase();
    badge.classList.remove('storage-supabase', 'storage-sqlite');
    if (normalized === 'supabase') {
      badge.classList.add('storage-supabase');
      if (textEl) textEl.textContent = 'Supabase';
      badge.title = 'Dữ liệu đang lưu trữ đám mây trên Supabase Cloud';
    } else {
      badge.classList.add('storage-sqlite');
      if (textEl) textEl.textContent = 'SQLite';
      badge.title = 'Dữ liệu đang lưu trữ cục bộ bằng SQLite';
    }
  }

  function updateHeaderTaskBadge(running, mode = 'normal') {
    const badge = document.getElementById('header-task-badge');
    const textEl = document.getElementById('header-task-text');
    if (!badge) return;

    badge.classList.toggle('task-running', Boolean(running));
    if (textEl) {
      if (running) {
        textEl.textContent = mode === 'resume' ? 'Đang chạy tiếp' : 'Đang chạy';
      } else {
        textEl.textContent = 'Sẵn sàng';
      }
    }
  }

  function updatePinLockButton() {
    const btnLock = document.getElementById('btn-pin-lock');
    if (!btnLock) return;
    const show = Boolean(configStatus.pin_required && getStoredPin());
    btnLock.style.display = show ? 'inline-flex' : 'none';
  }

  // ================= PIN Auth Modal =================
  function showPinModal(errorMsg = '') {
    const modal = document.getElementById('modal-pin-auth');
    const input = document.getElementById('input-access-pin');
    const errBox = document.getElementById('pin-auth-error');
    if (!modal) return;

    isAuthModalOpen = true;
    modal.style.display = 'flex';
    if (errBox) {
      if (errorMsg) {
        errBox.textContent = errorMsg;
        errBox.style.display = 'block';
      } else {
        errBox.textContent = '';
        errBox.style.display = 'none';
      }
    }
    if (input) {
      input.value = '';
      setTimeout(() => input.focus(), 60);
    }
  }

  function hidePinModal() {
    const modal = document.getElementById('modal-pin-auth');
    const errBox = document.getElementById('pin-auth-error');
    if (modal) modal.style.display = 'none';
    if (errBox) {
      errBox.textContent = '';
      errBox.style.display = 'none';
    }
    isAuthModalOpen = false;
  }

  async function verifyPinWithServer(pin) {
    try {
      const resp = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin })
      });
      if (!resp.ok) {
        return { ok: false, status: resp.status };
      }
      const data = await resp.json().catch(() => ({ ok: true }));
      return { ok: Boolean(data && (data.ok !== false && data.success !== false)), status: resp.status };
    } catch (err) {
      return { ok: false, error: err.message || 'Không thể kết nối máy chủ' };
    }
  }

  function bindPinModalEvents() {
    const form = document.getElementById('form-pin-auth');
    const input = document.getElementById('input-access-pin');
    const submitBtn = document.getElementById('btn-submit-pin');
    const errBox = document.getElementById('pin-auth-error');
    const btnLock = document.getElementById('btn-pin-lock');

    if (form && !form.dataset.bound) {
      form.dataset.bound = '1';
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pin = input ? input.value.trim() : '';
        if (!pin) {
          if (errBox) {
            errBox.textContent = 'Vui lòng nhập mã PIN truy cập.';
            errBox.style.display = 'block';
          }
          if (input) input.focus();
          return;
        }

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = '⏳ Đang xác thực...';
        }

        const result = await verifyPinWithServer(pin);

        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = '🔓 Mở khóa hệ thống';
        }

        if (result.ok) {
          setStoredPin(pin);
          hidePinModal();
          updatePinLockButton();
          wsShouldReconnect = true;
          connectWebSocket();
          markReady();
          notifyToast('Xác thực PIN thành công!', '🔓');
          if (typeof window.reloadWebAppData === 'function') {
            window.reloadWebAppData();
          }
        } else {
          setStoredPin('');
          updatePinLockButton();
          if (errBox) {
            errBox.textContent = result.error
              ? `Lỗi kết nối: ${result.error}`
              : 'Mã PIN không chính xác. Vui lòng thử lại!';
            errBox.style.display = 'block';
          }
          if (input) {
            input.classList.remove('input-shake');
            void input.offsetWidth;
            input.classList.add('input-shake');
            input.select();
            input.focus();
          }
        }
      });
    }

    if (btnLock && !btnLock.dataset.bound) {
      btnLock.dataset.bound = '1';
      btnLock.addEventListener('click', () => {
        lockSession();
      });
    }
  }

  function lockSession() {
    setStoredPin('');
    updatePinLockButton();
    wsShouldReconnect = false;
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
    }
    if (ws) {
      try { ws.close(1000, 'User locked session'); } catch (_e) {}
      ws = null;
    }
    updateWsBadge('offline', 'Đã khóa PIN');
    showPinModal('Phiên đã được khóa. Nhập mã PIN để tiếp tục.');
  }

  // ================= HTTP Fetch Wrapper =================
  async function apiFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const pin = getStoredPin();
    if (pin) {
      headers.set('X-Access-Pin', pin);
    }

    const resp = await fetch(path, {
      ...options,
      headers
    });

    if (resp.status === 401) {
      setStoredPin('');
      updatePinLockButton();
      if (!isAuthModalOpen) {
        showPinModal('Phiên hết hạn hoặc mã PIN không hợp lệ. Vui lòng nhập lại.');
      }
      throw new Error('Yêu cầu xác thực mã PIN (HTTP 401)');
    }

    const contentType = resp.headers.get('content-type') || '';
    let payload = null;
    if (contentType.includes('application/json')) {
      payload = await resp.json().catch(() => null);
    } else {
      payload = await resp.text().catch(() => '');
    }

    if (!resp.ok) {
      let msg = '';
      if (payload && typeof payload === 'object') {
        if (Array.isArray(payload.detail)) {
          msg = payload.detail.map(d => {
            const loc = Array.isArray(d.loc) ? d.loc.filter(x => x !== 'body').join('.') : '';
            return (loc ? `${loc}: ` : '') + (d.msg || JSON.stringify(d));
          }).join('; ');
        } else if (typeof payload.detail === 'string') {
          msg = payload.detail;
        } else if (payload.message) {
          msg = typeof payload.message === 'string' ? payload.message : JSON.stringify(payload.message);
        } else if (payload.error) {
          msg = typeof payload.error === 'string' ? payload.error : JSON.stringify(payload.error);
        }
      } else if (typeof payload === 'string' && payload.trim()) {
        msg = payload.trim();
      }
      if (!msg) msg = `HTTP ${resp.status}`;
      throw new Error(msg);
    }

    return payload;
  }

  // ================= WebSocket Connection =================
  function buildWsUrl() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const base = `${wsProtocol}//${window.location.host}/ws`;
    const pin = getStoredPin();
    return pin ? `${base}?pin=${encodeURIComponent(pin)}` : base;
  }

  function scheduleWsReconnect() {
    if (!wsShouldReconnect) return;
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer);

    const jitter = Math.floor(Math.random() * 400);
    const delay = Math.min(wsReconnectDelay + jitter, WS_MAX_DELAY_MS);
    const sec = Math.max(1, Math.round(delay / 1000));
    updateWsBadge('offline', `Thử lại sau ${sec}s...`);

    wsReconnectTimer = setTimeout(() => {
      wsReconnectTimer = null;
      connectWebSocket();
    }, delay);

    wsReconnectDelay = Math.min(wsReconnectDelay * 2, WS_MAX_DELAY_MS);
  }

  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    updateWsBadge('connecting', 'Đang kết nối...');

    try {
      ws = new WebSocket(buildWsUrl());
    } catch (err) {
      console.error('[WebAPI] WebSocket creation failed:', err);
      scheduleWsReconnect();
      return;
    }

    ws.onopen = () => {
      wsReconnectDelay = WS_BASE_DELAY_MS;
      updateWsBadge('online', 'WS Trực tuyến');
      if (wsHeartbeatTimer) clearInterval(wsHeartbeatTimer);
      wsHeartbeatTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          try { ws.send('ping'); } catch (_e) {}
        }
      }, 25000);
    };

    ws.onmessage = (evt) => {
      if (evt.data === 'pong') return;
      let msg = null;
      try {
        msg = JSON.parse(evt.data);
      } catch (_err) {
        return;
      }
      if (!msg || typeof msg !== 'object') return;

      const eventName = msg.event || msg.type;
      const data = msg.data !== undefined ? msg.data : msg.payload;

      if (eventName === 'task-status') {
        const running = Boolean(data && data.running);
        configStatus.running = running;
        updateHeaderTaskBadge(running, data && data.mode ? data.mode : 'normal');
        emitEvent('task-status', data || { running });
        return;
      }

      if (eventName === 'task-finished') {
        configStatus.running = false;
        updateHeaderTaskBadge(false);
        emitEvent('task-finished', data || { code: 0 });
        return;
      }

      if (eventName === 'log-message') {
        emitEvent('log-message', data || { text: '', type: 'normal', time: new Date().toLocaleTimeString() });
        return;
      }

      if (eventName === 'account-added') {
        emitEvent('account-added', data);
        return;
      }

      if (eventName === 'servers-updated') {
        emitEvent('servers-updated', data);
      }
    };

    ws.onerror = () => {
      // onclose will handle reconnect
    };

    ws.onclose = (evt) => {
      if (wsHeartbeatTimer) {
        clearInterval(wsHeartbeatTimer);
        wsHeartbeatTimer = null;
      }
      ws = null;
      // Unauthorized close codes from server
      if (evt.code === 4001 || evt.code === 4003 || evt.code === 1008) {
        wsShouldReconnect = false;
        setStoredPin('');
        updatePinLockButton();
        updateWsBadge('offline', 'Cần mã PIN');
        showPinModal('Kết nối WebSocket yêu cầu mã PIN hợp lệ.');
        return;
      }
      if (wsShouldReconnect) {
        scheduleWsReconnect();
      } else {
        updateWsBadge('offline', 'Đã ngắt kết nối');
      }
    };
  }

  // ================= Startup Initialization =================
  async function initWebBridge() {
    bindPinModalEvents();
    updateWsBadge('connecting', 'Đang kết nối...');

    try {
      const resp = await fetch('/api/config/status', { cache: 'no-store' });
      if (resp.ok) {
        const statusData = await resp.json();
        configStatus = {
          storage: statusData.storage || 'sqlite',
          running: Boolean(statusData.running),
          pin_required: Boolean(statusData.pin_required)
        };
      }
    } catch (err) {
      console.warn('[WebAPI] Failed to fetch /api/config/status:', err.message);
    }

    updateStorageBadge(configStatus.storage);
    updateHeaderTaskBadge(configStatus.running);
    updatePinLockButton();

    if (configStatus.pin_required) {
      const savedPin = getStoredPin();
      if (savedPin) {
        const verified = await verifyPinWithServer(savedPin);
        if (verified.ok) {
          updatePinLockButton();
          wsShouldReconnect = true;
          connectWebSocket();
          markReady();
          return;
        }
        setStoredPin('');
        updatePinLockButton();
      }
      updateWsBadge('offline', 'Chờ mã PIN');
      showPinModal();
      return;
    }

    // Open access mode
    wsShouldReconnect = true;
    connectWebSocket();
    markReady();
  }

  // ================= Clipboard & File Download Fallbacks =================
  async function copyToClipboardWeb(text) {
    const str = String(text ?? '');
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function' && window.isSecureContext) {
        await navigator.clipboard.writeText(str);
        return true;
      }
    } catch (_err) {
      // Fall through to textarea fallback
    }

    try {
      const ta = document.createElement('textarea');
      ta.value = str;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-9999px';
      ta.style.left = '-9999px';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return Boolean(ok);
    } catch (err) {
      console.error('[WebAPI] Clipboard fallback failed:', err);
      return false;
    }
  }

  async function exportTargetAccountsWeb(payload) {
    try {
      let fileContent = '';
      let fileNamePrefix = 'accounts_trung_pet';
      if (typeof payload === 'string') {
        fileContent = payload;
      } else if (payload && typeof payload === 'object') {
        fileContent = payload.content || '';
        if (payload.filename) fileNamePrefix = payload.filename;
      }

      const dateStr = new Date().toISOString().slice(0, 10);
      const fileName = fileNamePrefix.endsWith('.txt')
        ? fileNamePrefix
        : `${fileNamePrefix}_${dateStr}.txt`;

      const blob = new Blob([fileContent], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);

      return { success: true, fileName };
    } catch (err) {
      return { success: false, error: err.message || 'Lỗi tải xuống file' };
    }
  }

  // ================= Expose window.electronAPI =================
  window.electronAPI = {
    // Web-specific helpers
    isWebMode: true,
    waitForReady: () => readyPromise,
    getConfigStatus: () => ({ ...configStatus }),
    lockSession,

    // Task control
    startTask: async (config) => {
      try {
        const res = await apiFetch('/api/task/start', {
          method: 'POST',
          body: JSON.stringify(config || {})
        });
        if (res && res.success) {
          configStatus.running = true;
          updateHeaderTaskBadge(true, 'normal');
        }
        return res;
      } catch (err) {
        return { success: false, message: err.message || 'Không thể khởi động tiến trình' };
      }
    },

    stopTask: async () => {
      try {
        const res = await apiFetch('/api/task/stop', { method: 'POST' });
        if (res && res.success) {
          configStatus.running = false;
          updateHeaderTaskBadge(false);
        }
        return res;
      } catch (err) {
        return { success: false, message: err.message || 'Không thể dừng tiến trình' };
      }
    },

    resumePending: async (params) => {
      let body;
      if (typeof params === 'string') {
        body = { username: params };
      } else if (params && typeof params === 'object') {
        body = {
          username: params.username ?? null,
          threads: params.threads ?? 1,
          proxies: params.proxies ?? [],
          networkMode: params.networkMode ?? 'direct',
          proxyType: params.proxyType ?? 'socks5'
        };
      } else {
        body = { username: null };
      }

      try {
        const res = await apiFetch('/api/task/resume', {
          method: 'POST',
          body: JSON.stringify(body)
        });
        if (res && res.success) {
          configStatus.running = true;
          updateHeaderTaskBadge(true, 'resume');
        }
        return res;
      } catch (err) {
        return { success: false, message: err.message || 'Không thể chạy tiếp tài khoản' };
      }
    },

    // Server, Pokedex & Account Data
    getServers: async () => {
      const data = await apiFetch('/api/servers', { method: 'GET' });
      if (Array.isArray(data)) return data;
      if (data && Array.isArray(data.servers)) return data.servers;
      return [];
    },

    refreshServers: async () => {
      try {
        return await apiFetch('/api/servers/refresh', { method: 'POST' });
      } catch (err) {
        return { success: false, message: err.message || 'Không thể làm mới danh sách server' };
      }
    },

    getPokedex: async () => {
      const data = await apiFetch('/api/pokedex', { method: 'GET' });
      if (Array.isArray(data)) return data;
      if (data && Array.isArray(data.pokedex)) return data.pokedex;
      return [];
    },

    getAccounts: async () => {
      const data = await apiFetch('/api/accounts', { method: 'GET' });
      if (Array.isArray(data)) return data;
      if (data && Array.isArray(data.accounts)) return data.accounts;
      return [];
    },

    deleteAccount: async (username) => {
      if (!username) return false;
      try {
        const data = await apiFetch(`/api/accounts/${encodeURIComponent(String(username))}`, {
          method: 'DELETE'
        });
        if (typeof data === 'boolean') return data;
        return Boolean(data && (data.success !== undefined ? data.success : data.ok !== false));
      } catch (err) {
        console.error('[WebAPI] deleteAccount failed:', err);
        return false;
      }
    },

    deleteAccounts: async (usernames = []) => {
      try {
        const data = await apiFetch('/api/accounts/bulk-delete', {
          method: 'POST',
          body: JSON.stringify({ usernames: Array.isArray(usernames) ? usernames : [] })
        });
        if (typeof data === 'boolean') return data;
        return Boolean(data && (data.success !== undefined ? data.success : data.ok !== false));
      } catch (err) {
        console.error('[WebAPI] deleteAccounts failed:', err);
        return false;
      }
    },

    syncAccountPets: async (username) => {
      if (!username) {
        return { success: false, message: 'Tên tài khoản không hợp lệ!', pets: [], count: 0 };
      }
      try {
        return await apiFetch(`/api/accounts/${encodeURIComponent(String(username).trim())}/sync-pets`, {
          method: 'POST'
        });
      } catch (err) {
        return {
          success: false,
          username,
          message: err.message || 'Lỗi đồng bộ kho Pet',
          pets: [],
          count: 0
        };
      }
    },

    getSavedProxies: async () => {
      try {
        return await apiFetch('/api/proxies', { method: 'GET' });
      } catch (err) {
        console.warn('[WebAPI] getSavedProxies failed:', err);
        return { success: false, proxies: [], total: 0, alive: 0, dead: 0 };
      }
    },

    saveProxies: async (data = {}) => {
      try {
        return await apiFetch('/api/proxies', {
          method: 'PUT',
          body: JSON.stringify({
            proxies: data.proxies ?? [],
            type: data.type || 'http'
          })
        });
      } catch (err) {
        console.warn('[WebAPI] saveProxies failed:', err);
        return { success: false, message: err.message || 'Lỗi lưu proxy' };
      }
    },

    clearSavedProxies: async () => {
      try {
        return await apiFetch('/api/proxies', { method: 'DELETE' });
      } catch (err) {
        console.warn('[WebAPI] clearSavedProxies failed:', err);
        return { success: false };
      }
    },

    checkProxies: async (data = {}) => {
      try {
        return await apiFetch('/api/proxies/check', {
          method: 'POST',
          body: JSON.stringify({
            proxies: data.proxies ?? [],
            type: data.type || 'http'
          })
        });
      } catch (err) {
        return {
          success: false,
          message: err.message || 'Lỗi kiểm tra proxy',
          total: 0,
          alive: 0,
          dead: 0,
          results: []
        };
      }
    },

    // Browser Clipboard & File Fallbacks
    copyToClipboard: copyToClipboardWeb,
    exportTargetAccounts: exportTargetAccountsWeb,

    openExportFile: async () => {
      notifyToast('Trên bản Web, hãy dùng nút "📋 Copy All" hoặc "💾 Tải .txt" để xuất danh sách tài khoản.', 'ℹ️');
      return { success: true, webFallback: true };
    },

    openExportFolder: async () => {
      notifyToast('Trình duyệt không hỗ trợ mở thư mục máy chủ. Hãy dùng nút tải file .txt trực tiếp!', 'ℹ️');
      return { success: true, webFallback: true };
    },

    // Realtime Events
    onLog: (callback) => {
      if (typeof callback === 'function') listeners['log-message'].push(callback);
    },
    onTaskFinished: (callback) => {
      if (typeof callback === 'function') listeners['task-finished'].push(callback);
    },
    onAccountAdded: (callback) => {
      if (typeof callback === 'function') listeners['account-added'].push(callback);
    },
    onServersUpdated: (callback) => {
      if (typeof callback === 'function') listeners['servers-updated'].push(callback);
    },
    onTaskStatus: (callback) => {
      if (typeof callback === 'function') listeners['task-status'].push(callback);
    },

    // Electron window controls -> clean no-ops in browser
    minimize: () => {},
    maximize: () => {},
    close: () => {}
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWebBridge, { once: true });
  } else {
    initWebBridge();
  }
})();
