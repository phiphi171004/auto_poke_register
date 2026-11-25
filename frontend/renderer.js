// ========================================================
// POKEMON MASTER AUTO WEB PRO - RENDERER CONTROLLER
// ========================================================

const LEGENDARY_PETS = new Set([
  'Groudon', 'Kyogre', 'Rayquaza', 'Cresselia', 'Meloetta', 'Mewtwo', 'Mew',
  'Deoxys', 'Lugia', 'Ho-oh', 'Celebi', 'Jirachi', 'Latios', 'Latias',
  'Dialga', 'Palkia', 'Giratina', 'Darkrai', 'Arceus', 'Reshiram', 'Zekrom',
  'Kyurem', 'Xerneas', 'Yveltal', 'Zygarde', 'Solgaleo', 'Lunala', 'Necrozma',
  'Zacian', 'Zamazenta', 'Eternatus', 'Articuno', 'Zapdos', 'Moltres',
  'Raikou', 'Entei', 'Suicune', 'Regirock', 'Regice', 'Registeel',
  'Tapu Koko', 'Tapu Lele', 'Tapu Bulu', 'Tapu Fini', 'Cosmog', 'Marshadow', 'Zeraora',
  'Uxie', 'Mesprit', 'Azelf', 'Heatran', 'Regigigas', 'Phione', 'Manaphy', 'Shaymin',
  'Cobalion', 'Terrakion', 'Virizion', 'Tornadus', 'Thundurus', 'Landorus', 'Keldeo', 'Genesect',
  'Diancie', 'Hoopa', 'Volcanion'
]);

const RARE_PETS = new Set([
  'Dratini', 'Dragonair', 'Dragonite', 'Larvitar', 'Pupitar', 'Tyranitar',
  'Bagon', 'Shelgon', 'Salamence', 'Beldum', 'Metang', 'Metagross',
  'Gible', 'Gabite', 'Garchomp', 'Deino', 'Zweilous', 'Hydreigon',
  'Charmander', 'Charmeleon', 'Charizard', 'Squirtle', 'Blastoise',
  'Bulbasaur', 'Venusaur', 'Pikachu', 'Raichu', 'Onix', 'Steelix',
  'Altaria', 'Medicham', 'Seel', 'Dewpider', 'Carvanha', 'Sharpedo',
  'Swablu', 'Buneary', 'Lopunny', 'Emolga', 'Shinx', 'Luxio', 'Luxray',
  'Trapinch', 'Flygon', 'Kabuto', 'Kabutops', 'Omanyte', 'Omastar',
  'Aerodactyl', 'Snorlax', 'Lapras', 'Ditto', 'Eevee', 'Vaporeon',
  'Jolteon', 'Flareon', 'Espeon', 'Umbreon', 'Leafeon', 'Glaceon', 'Sylveon',
  'Lucario', 'Riolu', 'Milotic', 'Feebas', 'Absol', 'Rotom', 'Togekiss',
  'Electivire', 'Magmortar', 'Magnezone', 'Gliscor', 'Mamoswine', 'Gallade',
  'Axew', 'Haxorus', 'Zorua', 'Zoroark', 'Greninja', 'Volcarona'
]);

let fullPokedex = [];

// Safe localStorage helpers (prevent crashes in restricted privacy modes)
function safeStorageGet(key, fallback = null) {
  try {
    const val = localStorage.getItem(key);
    return val !== null ? val : fallback;
  } catch (_err) {
    return fallback;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch (_err) {
    // Ignore storage quota errors
  }
}

// ========================================================
// POKEMON NATURE / PERSONALITY (TÍNH CÁCH) MASTER MAP
// ========================================================
const NATURE_MAP = {
  // ── Tấn công (+DAM) ──
  1001: { id: 1001, name: 'Cô Đơn', en: 'Lonely', buff: 'DAM+10%', nerf: 'DEF-10%', type: 'dam', meta: false, desc: 'Tăng Tấn công (+10%), giảm Thủ vật lý (-10%)' },
  1002: { id: 1002, name: 'Cứng', en: 'Adamant', buff: 'DAM+10%', nerf: 'CRIT-10%', type: 'dam', meta: true, desc: 'Tăng Tấn công (+10%), giảm Đặc công (-10%) [Chuẩn Meta Vật lý]' },
  1003: { id: 1003, name: 'Nghịch', en: 'Naughty', buff: 'DAM+10%', nerf: 'ARM-10%', type: 'dam', meta: false, desc: 'Tăng Tấn công (+10%), giảm Kháng phép (-10%)' },
  1004: { id: 1004, name: 'Dũng', en: 'Brave', buff: 'DAM+10%', nerf: 'SPEED-10%', type: 'dam', meta: false, desc: 'Tăng Tấn công (+10%), giảm Tốc độ (-10%)' },

  // ── Thủ vật lý (+DEF) ──
  1005: { id: 1005, name: 'Gan Dạ', en: 'Bold', buff: 'DEF+10%', nerf: 'DAM-10%', type: 'def', meta: true, desc: 'Tăng Thủ vật lý (+10%), giảm Tấn công (-10%) [Chuẩn Meta Tanker Phép]' },
  1006: { id: 1006, name: 'Bướng', en: 'Impish', buff: 'DEF+10%', nerf: 'CRIT-10%', type: 'def', meta: true, desc: 'Tăng Thủ vật lý (+10%), giảm Đặc công (-10%) [Chuẩn Meta Tanker Vật lý]' },
  1007: { id: 1007, name: 'Vô Tư', en: 'Lax', buff: 'DEF+10%', nerf: 'ARM-10%', type: 'def', meta: false, desc: 'Tăng Thủ vật lý (+10%), giảm Kháng phép (-10%)' },
  1008: { id: 1008, name: 'Nhàn', en: 'Relaxed', buff: 'DEF+10%', nerf: 'SPEED-10%', type: 'def', meta: false, desc: 'Tăng Thủ vật lý (+10%), giảm Tốc độ (-10%)' },

  // ── Đặc công (+CRIT) ──
  1009: { id: 1009, name: 'Bảo Thủ', en: 'Modest', buff: 'CRIT+10%', nerf: 'DAM-10%', type: 'crit', meta: true, desc: 'Tăng Đặc công (+10%), giảm Tấn công (-10%) [Chuẩn Meta Công Phép]' },
  1010: { id: 1010, name: 'Vững', en: 'Mild', buff: 'CRIT+10%', nerf: 'DEF-10%', type: 'crit', meta: false, desc: 'Tăng Đặc công (+10%), giảm Thủ vật lý (-10%)' },
  1011: { id: 1011, name: 'Vô Tâm', en: 'Rash', buff: 'CRIT+10%', nerf: 'ARM-10%', type: 'crit', meta: false, desc: 'Tăng Đặc công (+10%), giảm Kháng phép (-10%)' },
  1012: { id: 1012, name: 'Im', en: 'Quiet', buff: 'CRIT+10%', nerf: 'SPEED-10%', type: 'crit', meta: false, desc: 'Tăng Đặc công (+10%), giảm Tốc độ (-10%)' },

  // ── Kháng phép (+ARM) ──
  1013: { id: 1013, name: 'Trầm', en: 'Calm', buff: 'ARM+10%', nerf: 'DAM-10%', type: 'arm', meta: true, desc: 'Tăng Kháng phép (+10%), giảm Tấn công (-10%) [Chuẩn Meta Kháng Phép]' },
  1014: { id: 1014, name: 'Ngoan', en: 'Gentle', buff: 'ARM+10%', nerf: 'DEF-10%', type: 'arm', meta: false, desc: 'Tăng Kháng phép (+10%), giảm Thủ vật lý (-10%)' },
  1015: { id: 1015, name: 'Cẩn Thận', en: 'Careful', buff: 'ARM+10%', nerf: 'CRIT-10%', type: 'arm', meta: true, desc: 'Tăng Kháng phép (+10%), giảm Đặc công (-10%) [Chuẩn Meta Kháng Phép Vật Lý]' },
  1016: { id: 1016, name: 'Ngạo', en: 'Sassy', buff: 'ARM+10%', nerf: 'SPEED-10%', type: 'arm', meta: false, desc: 'Tăng Kháng phép (+10%), giảm Tốc độ (-10%)' },

  // ── Tốc độ (+SPEED) ──
  1017: { id: 1017, name: 'Nhát', en: 'Timid', buff: 'SPEED+10%', nerf: 'DAM-10%', type: 'speed', meta: true, desc: 'Tăng Tốc độ (+10%), giảm Tấn công (-10%) [Chuẩn Meta Nhanh Phép]' },
  1018: { id: 1018, name: 'Nóng', en: 'Hasty', buff: 'SPEED+10%', nerf: 'DEF-10%', type: 'speed', meta: false, desc: 'Tăng Tốc độ (+10%), giảm Thủ vật lý (-10%)' },
  1019: { id: 1019, name: 'Cởi Mở', en: 'Jolly', buff: 'SPEED+10%', nerf: 'CRIT-10%', type: 'speed', meta: true, desc: 'Tăng Tốc độ (+10%), giảm Đặc công (-10%) [Chuẩn Meta Nhanh Vật lý]' },
  1020: { id: 1020, name: 'Ngây Thơ', en: 'Naive', buff: 'SPEED+10%', nerf: 'ARM-10%', type: 'speed', meta: false, desc: 'Tăng Tốc độ (+10%), giảm Kháng phép (-10%)' },

  // ── Cân bằng (Neutral) ──
  1021: { id: 1021, name: 'Ngại', en: 'Bashful', buff: '', nerf: '', type: 'neutral', meta: false, desc: 'Cân bằng, không tăng giảm chỉ số' },
  1022: { id: 1022, name: 'Thật', en: 'Docile', buff: '', nerf: '', type: 'neutral', meta: false, desc: 'Cân bằng, không tăng giảm chỉ số' },
  1023: { id: 1023, name: 'Thẳng', en: 'Hardy', buff: '', nerf: '', type: 'neutral', meta: false, desc: 'Cân bằng, không tăng giảm chỉ số' },
  1024: { id: 1024, name: 'Xốc Nổi', en: 'Quirky', buff: '', nerf: '', type: 'neutral', meta: false, desc: 'Cân bằng, không tăng giảm chỉ số' },
  1025: { id: 1025, name: 'Nghiêm', en: 'Serious', buff: '', nerf: '', type: 'neutral', meta: false, desc: 'Cân bằng, không tăng giảm chỉ số' }
};

// Auto-register Enhanced Natures (1026-1050)
for (let bId = 1001; bId <= 1025; bId++) {
  const b = NATURE_MAP[bId];
  const enhId = bId + 25;
  NATURE_MAP[enhId] = {
    id: enhId,
    name: `Rất ${b.name}`,
    en: `Very ${b.en}`,
    buff: b.buff ? b.buff.replace('10%', '20%') : '',
    nerf: b.nerf ? b.nerf.replace('10%', '10%') : '',
    type: b.type,
    meta: b.meta,
    desc: `Tính cách tiến cấp: ${b.desc}`
  };
}

const parsedPetCache = new Map();

function parsePetEntry(petRaw) {
  if (!petRaw) return { name: '', natureId: 0, nature: null, raw: '' };
  if (typeof petRaw === 'object' && petRaw.name) return petRaw;

  const rawStr = String(petRaw).trim();
  const cached = parsedPetCache.get(rawStr);
  if (cached) return cached;

  let parsed;
  const hashIdx = rawStr.indexOf('#');
  if (hashIdx !== -1) {
    const name = rawStr.slice(0, hashIdx).trim();
    const nid = parseInt(rawStr.slice(hashIdx + 1), 10) || 0;
    parsed = {
      name,
      natureId: nid,
      nature: NATURE_MAP[nid] || null,
      raw: rawStr
    };
  } else {
    parsed = {
      name: rawStr,
      natureId: 0,
      nature: null,
      raw: rawStr
    };
  }

  if (parsedPetCache.size > 25000) {
    parsedPetCache.clear();
  }
  parsedPetCache.set(rawStr, parsed);
  return parsed;
}

// State
let isRunning = false;
let accountsList = [];
let allServers = [];
let currentLogFilter = 'all';
const proxyCheckCache = new Map();

// Multi-threading & Proxy DOM Elements
const inputThreads = document.getElementById('input-threads');
const inputThreadsRange = document.getElementById('input-threads-range');
const threadsDisplay = document.getElementById('threads-display');
const radioNetDirect = document.getElementById('radio-net-direct');
const radioNetProxy = document.getElementById('radio-net-proxy');
const lblNetDirect = document.getElementById('lbl-net-direct');
const lblNetProxy = document.getElementById('lbl-net-proxy');
const proxyDetailsBox = document.getElementById('proxy-details-box');
const selectProxyType = document.getElementById('select-proxy-type');
const textareaProxies = document.getElementById('textarea-proxies');
const btnCheckProxies = document.getElementById('btn-check-proxies');
const btnClearProxies = document.getElementById('btn-clear-proxies');
const selectNatureFilter = document.getElementById('select-nature-filter');
const badgeNatureCount = document.getElementById('badge-nature-count');
const proxyCountBadge = document.getElementById('proxy-count-badge');
const proxyCheckStatus = document.getElementById('proxy-check-status');
const proxyModeBadge = document.getElementById('proxy-mode-badge');

const inputSearchServer = document.getElementById('input-search-server');
const selectServer = document.getElementById('select-server');
const lblSelectServer = document.getElementById('lbl-select-server');
const btnRefreshServers = document.getElementById('btn-refresh-servers');
const endpointText = document.getElementById('endpoint-text');
const badgeZoneId = document.getElementById('badge-zone-id');
const inputZone = document.getElementById('input-zone');
const inputCount = document.getElementById('input-count');
const inputCountRange = document.getElementById('input-count-range');
const countDisplay = document.getElementById('count-display');
const inputDelayMin = document.getElementById('input-delay-min');
const inputDelayMax = document.getElementById('input-delay-max');
const inputRateLimit = document.getElementById('input-rate-limit');
const rateLimitBadge = document.getElementById('rate-limit-badge');

// Restore speed & count UI settings from localStorage
const savedRateLimit = safeStorageGet('pokemon_master_rate_limit');
if (savedRateLimit && inputRateLimit) {
  inputRateLimit.value = savedRateLimit;
}
const savedCount = safeStorageGet('pokemon_master_count');
if (savedCount && inputCount && inputCountRange && countDisplay) {
  const cVal = Math.max(1, parseInt(savedCount, 10) || 100);
  inputCount.value = cVal;
  inputCountRange.value = Math.min(cVal, parseInt(inputCountRange.max, 10) || 100);
  countDisplay.textContent = String(cVal);
}
const savedDelayMin = safeStorageGet('pokemon_master_delay_min');
if (savedDelayMin && inputDelayMin) inputDelayMin.value = savedDelayMin;
const savedDelayMax = safeStorageGet('pokemon_master_delay_max');
if (savedDelayMax && inputDelayMax) inputDelayMax.value = savedDelayMax;

if (inputDelayMin) {
  inputDelayMin.addEventListener('input', () => safeStorageSet('pokemon_master_delay_min', inputDelayMin.value));
}
if (inputDelayMax) {
  inputDelayMax.addEventListener('input', () => safeStorageSet('pokemon_master_delay_max', inputDelayMax.value));
}

function updateRateLimitBadge() {
  if (!inputRateLimit || !rateLimitBadge) return;
  const val = parseInt(inputRateLimit.value, 10) || 100;
  if (val >= 80) {
    rateLimitBadge.textContent = '⚡ Siêu tốc';
    rateLimitBadge.style.background = 'rgba(6, 182, 212, 0.2)';
    rateLimitBadge.style.color = '#38bdf8';
  } else if (val >= 40) {
    rateLimitBadge.textContent = '🚀 Nhanh';
    rateLimitBadge.style.background = 'rgba(16, 185, 129, 0.2)';
    rateLimitBadge.style.color = '#34d399';
  } else {
    rateLimitBadge.textContent = '🛡️ An toàn IP';
    rateLimitBadge.style.background = 'rgba(234, 179, 8, 0.2)';
    rateLimitBadge.style.color = '#fde047';
  }
}

if (inputRateLimit) {
  updateRateLimitBadge();
  inputRateLimit.addEventListener('input', () => {
    safeStorageSet('pokemon_master_rate_limit', inputRateLimit.value);
    updateRateLimitBadge();
  });
}

// Target Pet Filter DOM
const btnModeCustom = document.getElementById('btn-mode-custom');
const btnModeLegendary = document.getElementById('btn-mode-legendary');
const customPetControls = document.getElementById('custom-pet-controls');
const legendaryModeBox = document.getElementById('legendary-mode-box');
const selectedPetsContainer = document.getElementById('selected-pets-container');
const inputTargetPet = document.getElementById('input-target-pet');
const btnClearTargetInput = document.getElementById('btn-clear-target-input');
const petSuggestions = document.getElementById('pet-suggestions');
const chkFilterOnlyTargets = document.getElementById('chk-filter-only-targets');
const chkMatchAllPets = document.getElementById('chk-match-all-pets');
const boxMatchAllPets = document.getElementById('box-match-all-pets');
const quickTags = document.querySelectorAll('.quick-tag');
const accPills = document.querySelectorAll('.acc-pill');
const countTargetHits = document.getElementById('count-target-hits');
const countTargetMiss = document.getElementById('count-target-miss');
const countTargetPending = document.getElementById('count-target-pending');
const countResumePending = document.getElementById('count-resume-pending');
const btnResumePending = document.getElementById('btn-resume-pending');
const btnDeleteFailed = document.getElementById('btn-delete-failed') || document.getElementById('btn-smart-delete');
const btnDownloadTxt = document.getElementById('btn-download-txt');

const STORAGE_KEY_MATCH_ALL_PETS = 'pokemon_master_match_all_pets';

// Clear legacy Lucky Sigh item filter storage (event ended)
try { localStorage.removeItem('pokemon_master_selected_lucky_items'); } catch (_e) {}

let currentAccFilter = 'target';
let currentFilteredAccounts = [];
let targetFilterMode = safeStorageGet('pokemon_master_filter_mode', 'custom');
let selectedPetSet = new Set();

const savedPetsStr = safeStorageGet('pokemon_master_selected_pets');
if (savedPetsStr) {
  try {
    const arr = JSON.parse(savedPetsStr);
    if (Array.isArray(arr) && arr.length > 0) {
      arr.forEach(p => selectedPetSet.add(p));
    } else {
      selectedPetSet.add('Shinx');
    }
  } catch (_e) {
    selectedPetSet.add('Shinx');
  }
} else {
  selectedPetSet.add('Shinx');
}

const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

const metricAccounts = document.getElementById('metric-accounts');
const metricDraws = document.getElementById('metric-draws');
const metricPets = document.getElementById('metric-pets');
const metricLegendaries = document.getElementById('metric-legendaries');
const accTabBadge = document.getElementById('acc-tab-badge');

const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

const consoleLogs = document.getElementById('console-logs');
const chkAutoscroll = document.getElementById('chk-autoscroll');
const btnClearConsole = document.getElementById('btn-clear-console');
const filterButtons = document.querySelectorAll('.filter-btn');

const inputSearchAcc = document.getElementById('input-search-acc');
const accountsTableScroll = document.getElementById('accounts-table-scroll');
const accountsTbody = document.getElementById('accounts-tbody');
const accPaginationInfo = document.getElementById('acc-pagination-info');
const selectAccPageSize = document.getElementById('select-acc-page-size');
const btnAccPageFirst = document.getElementById('btn-acc-page-first');
const btnAccPagePrev = document.getElementById('btn-acc-page-prev');
const accPaginationPages = document.getElementById('acc-pagination-pages');
const btnAccPageNext = document.getElementById('btn-acc-page-next');
const btnAccPageLast = document.getElementById('btn-acc-page-last');
const btnExportTxt = document.getElementById('btn-export-txt');
const btnOpenFolder = document.getElementById('btn-open-folder');

const STORAGE_KEY_ACC_PAGE_SIZE = 'pokemon_master_acc_page_size';
const ALLOWED_ACC_PAGE_SIZES = [50, 100, 200];
let currentAccPage = 1;
let accPageSize = (() => {
  const saved = parseInt(safeStorageGet(STORAGE_KEY_ACC_PAGE_SIZE, '50'), 10);
  return ALLOWED_ACC_PAGE_SIZES.includes(saved) ? saved : 50;
})();
if (selectAccPageSize) {
  selectAccPageSize.value = String(accPageSize);
}
let searchAccDebounceTimer = null;

const petsCollection = document.getElementById('pets-collection');
const toastContainer = document.getElementById('toast-container');

// ================= Account & Password Config =================
const chkRandomUsername = document.getElementById('chk-random-username');
const inputCustomUsername = document.getElementById('input-custom-username');
const chkRandomPassword = document.getElementById('chk-random-password');
const inputCustomPassword = document.getElementById('input-custom-password');

const STORAGE_KEY_RANDOM_USER = 'pokemon_master_random_user';
const STORAGE_KEY_AUTO_INC = 'pokemon_master_auto_increment_user';
const chkAutoIncrementUsername = document.getElementById('chk-auto-increment-username');
const boxAutoIncrement = document.getElementById('box-auto-increment');
const STORAGE_KEY_CUSTOM_USER = 'pokemon_master_custom_user';
const STORAGE_KEY_RANDOM_PASS = 'pokemon_master_random_pass';
const STORAGE_KEY_CUSTOM_PASS = 'pokemon_master_custom_pass';

function setupAccountCredentialsUI() {
  if (!chkRandomUsername || !inputCustomUsername || !chkRandomPassword || !inputCustomPassword) return;

  const savedRandomUser = safeStorageGet(STORAGE_KEY_RANDOM_USER);
  const savedCustomUser = safeStorageGet(STORAGE_KEY_CUSTOM_USER);
  if (savedRandomUser !== null) {
    chkRandomUsername.checked = savedRandomUser === 'true';
  }
  if (savedCustomUser !== null) {
    inputCustomUsername.value = savedCustomUser;
  }
  const savedAutoInc = safeStorageGet(STORAGE_KEY_AUTO_INC);
  if (savedAutoInc !== null && chkAutoIncrementUsername) {
    chkAutoIncrementUsername.checked = savedAutoInc === 'true';
  }
  if (chkAutoIncrementUsername) {
    chkAutoIncrementUsername.addEventListener('change', () => {
      safeStorageSet(STORAGE_KEY_AUTO_INC, chkAutoIncrementUsername.checked);
    });
  }
  updateUsernameInputState();

  const savedRandomPass = safeStorageGet(STORAGE_KEY_RANDOM_PASS);
  const savedCustomPass = safeStorageGet(STORAGE_KEY_CUSTOM_PASS);
  if (savedRandomPass !== null) {
    chkRandomPassword.checked = savedRandomPass === 'true';
  }
  if (savedCustomPass !== null) {
    inputCustomPassword.value = savedCustomPass;
  }
  updatePasswordInputState();

  chkRandomUsername.addEventListener('change', () => {
    safeStorageSet(STORAGE_KEY_RANDOM_USER, chkRandomUsername.checked);
    updateUsernameInputState();
    if (!chkRandomUsername.checked) inputCustomUsername.focus();
  });

  inputCustomUsername.addEventListener('input', () => {
    safeStorageSet(STORAGE_KEY_CUSTOM_USER, inputCustomUsername.value.trim());
  });

  chkRandomPassword.addEventListener('change', () => {
    safeStorageSet(STORAGE_KEY_RANDOM_PASS, chkRandomPassword.checked);
    updatePasswordInputState();
    if (!chkRandomPassword.checked) inputCustomPassword.focus();
  });

  inputCustomPassword.addEventListener('input', () => {
    safeStorageSet(STORAGE_KEY_CUSTOM_PASS, inputCustomPassword.value.trim());
  });
}

function updateUsernameInputState() {
  if (!chkRandomUsername || !inputCustomUsername) return;
  const isRandom = chkRandomUsername.checked;
  inputCustomUsername.disabled = isRandom;
  inputCustomUsername.placeholder = isRandom ? 'Đang bật Random tự động...' : 'Nhập username cố định (vd: kaf100000)...';
  if (boxAutoIncrement) {
    boxAutoIncrement.style.display = isRandom ? 'none' : 'block';
  }
}

function updatePasswordInputState() {
  if (!chkRandomPassword || !inputCustomPassword) return;
  const isRandom = chkRandomPassword.checked;
  inputCustomPassword.disabled = isRandom;
  inputCustomPassword.placeholder = isRandom ? 'Đang bật Random tự động...' : 'Nhập mật khẩu cố định...';
}

// ================= Multi-threading & Proxy Config =================
const STORAGE_KEY_THREADS = 'pokemon_master_threads';
const STORAGE_KEY_NET_MODE = 'pokemon_master_net_mode';
const STORAGE_KEY_PROXY_TYPE = 'pokemon_master_proxy_type';
const STORAGE_KEY_PROXIES = 'pokemon_master_proxies';

function setupMultiThreadingAndProxyUI() {
  if (inputThreads && inputThreadsRange && threadsDisplay) {
    const savedThreads = safeStorageGet(STORAGE_KEY_THREADS);
    if (savedThreads) {
      const val = Math.max(1, parseInt(savedThreads, 10) || 1);
      inputThreads.value = val;
      if (val > parseInt(inputThreadsRange.max, 10)) {
        inputThreadsRange.max = val;
      }
      inputThreadsRange.value = val;
      threadsDisplay.textContent = `${val} luồng`;
    }

    inputThreadsRange.addEventListener('input', () => {
      const val = parseInt(inputThreadsRange.value, 10) || 1;
      inputThreads.value = val;
      threadsDisplay.textContent = `${val} luồng`;
      safeStorageSet(STORAGE_KEY_THREADS, val);
    });

    inputThreads.addEventListener('input', () => {
      const val = Math.max(1, parseInt(inputThreads.value, 10) || 1);
      if (val > parseInt(inputThreadsRange.max, 10)) {
        inputThreadsRange.max = val;
      }
      inputThreadsRange.value = val;
      threadsDisplay.textContent = `${val} luồng`;
      safeStorageSet(STORAGE_KEY_THREADS, val);
    });
  }

  function setNetworkMode(mode) {
    if (mode === 'proxy') {
      if (radioNetProxy) radioNetProxy.checked = true;
      if (lblNetProxy) lblNetProxy.classList.add('active');
      if (lblNetDirect) lblNetDirect.classList.remove('active');
      if (proxyDetailsBox) proxyDetailsBox.style.display = 'block';
      if (proxyModeBadge) {
        proxyModeBadge.textContent = 'Proxy';
        proxyModeBadge.style.background = 'rgba(168, 85, 247, 0.2)';
        proxyModeBadge.style.color = '#c084fc';
      }
    } else {
      if (radioNetDirect) radioNetDirect.checked = true;
      if (lblNetDirect) lblNetDirect.classList.add('active');
      if (lblNetProxy) lblNetProxy.classList.remove('active');
      if (proxyDetailsBox) proxyDetailsBox.style.display = 'none';
      if (proxyModeBadge) {
        proxyModeBadge.textContent = 'Mạng gốc';
        proxyModeBadge.style.background = 'rgba(56, 189, 248, 0.15)';
        proxyModeBadge.style.color = '#38bdf8';
      }
    }
    safeStorageSet(STORAGE_KEY_NET_MODE, mode);
  }

  if (radioNetDirect) {
    radioNetDirect.addEventListener('change', () => setNetworkMode('direct'));
  }
  if (radioNetProxy) {
    radioNetProxy.addEventListener('change', () => setNetworkMode('proxy'));
  }

  const savedNetMode = safeStorageGet(STORAGE_KEY_NET_MODE);
  if (savedNetMode) {
    setNetworkMode(savedNetMode);
  }

  if (selectProxyType) {
    const savedType = safeStorageGet(STORAGE_KEY_PROXY_TYPE);
    if (savedType) selectProxyType.value = savedType;
    selectProxyType.addEventListener('change', () => {
      safeStorageSet(STORAGE_KEY_PROXY_TYPE, selectProxyType.value);
      scheduleSaveProxiesToDb();
    });
  }

  let proxyDbSaveTimer = null;
  function scheduleSaveProxiesToDb(immediate = false) {
    if (!window.electronAPI || typeof window.electronAPI.saveProxies !== 'function') return;
    if (proxyDbSaveTimer) {
      clearTimeout(proxyDbSaveTimer);
      proxyDbSaveTimer = null;
    }
    const doSave = () => {
      const lines = textareaProxies
        ? textareaProxies.value.split('\n').map(l => l.trim()).filter(l => l.length > 0 && !l.startsWith('#'))
        : [];
      const type = selectProxyType ? selectProxyType.value : 'http';
      window.electronAPI.saveProxies({ proxies: lines, type }).catch(() => {});
    };
    if (immediate) {
      doSave();
    } else {
      proxyDbSaveTimer = setTimeout(doSave, 800);
    }
  }

  function updateProxyCountBadge() {
    if (!textareaProxies || !proxyCountBadge) return;
    const lines = textareaProxies.value.split('\n').map(l => l.trim()).filter(l => l.length > 0 && !l.startsWith('#'));
    proxyCountBadge.textContent = `${lines.length} proxy`;
    safeStorageSet(STORAGE_KEY_PROXIES, textareaProxies.value);
  }

  if (textareaProxies) {
    const savedProxies = safeStorageGet(STORAGE_KEY_PROXIES);
    if (savedProxies) {
      textareaProxies.value = savedProxies;
    }
    updateProxyCountBadge();
    textareaProxies.addEventListener('input', () => {
      updateProxyCountBadge();
      scheduleSaveProxiesToDb(false);
    });
  }

  if (btnClearProxies) {
    btnClearProxies.addEventListener('click', () => {
      if (textareaProxies) {
        textareaProxies.value = '';
        updateProxyCountBadge();
      }
      proxyCheckCache.clear();
      if (window.electronAPI && typeof window.electronAPI.clearSavedProxies === 'function') {
        window.electronAPI.clearSavedProxies().catch(() => {});
      }
      if (proxyCheckStatus) {
        proxyCheckStatus.innerHTML = 'Danh sách proxy đã được xóa sạch (cả trên CSDL).';
      }
      renderThreadProxyMapping();
      showToast('Đã xóa toàn bộ proxy trong danh sách và CSDL', '🗑️');
    });
  }

  if (btnCheckProxies) {
    btnCheckProxies.addEventListener('click', async () => {
      if (!textareaProxies) return;
      const rawText = textareaProxies.value;
      const lines = rawText.split('\n').map(l => l.trim()).filter(l => l.length > 0 && !l.startsWith('#'));
      if (lines.length === 0) {
        showToast('Vui lòng nhập hoặc dán ít nhất 1 proxy trước khi kiểm tra!', '⚠️');
        textareaProxies.focus();
        return;
      }

      btnCheckProxies.disabled = true;
      if (proxyCheckStatus) {
        proxyCheckStatus.innerHTML = '<span style="color: #38bdf8;">⏳ Đang kiểm tra kết nối các proxy...</span>';
      }

      try {
        const type = selectProxyType ? selectProxyType.value : 'socks5';
        const res = await window.electronAPI.checkProxies({ proxies: lines, type });
        if (res && res.success) {
          proxyCheckCache.clear();
          (res.results || []).forEach(r => {
            proxyCheckCache.set(r.proxy, r);
            const parts = String(r.proxy || '').split(':');
            if (parts.length >= 2) {
              proxyCheckCache.set(`${parts[0]}:${parts[1]}`, r);
            }
          });

          renderThreadProxyMapping();

          const aliveItems = (res.results || []).filter(r => r.alive);
          const deadItems = (res.results || []).filter(r => !r.alive);
          let avgPing = 0;
          if (aliveItems.length > 0) {
            avgPing = Math.round(aliveItems.reduce((acc, cur) => acc + (cur.latency || 0), 0) / aliveItems.length);
          }
          const pingInfo = aliveItems.length > 0 ? `Ping TB: ~${avgPing}ms` : '';

          let html = `
            <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 4px;">
              <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
                <div>
                  <span style="color: #34d399; font-weight: 600;">✅ Hoạt động: ${res.alive}/${res.total}</span>
                  <span style="color: ${res.dead > 0 ? '#f87171' : '#94a3b8'}; margin-left: 8px; font-weight: 600;">
                    ${res.dead > 0 ? '❌ Lỗi/Chết: ' + res.dead : '❌ Không có lỗi'}
                  </span>
                  ${pingInfo ? `<span style="color: #94a3b8; margin-left: 8px;">| ${pingInfo}</span>` : ''}
                  <span style="color: #38bdf8; margin-left: 8px; font-size: 11px;">💾 Đã lưu CSDL</span>
                </div>
                ${deadItems.length > 0 ? `
                  <button type="button" id="btn-remove-dead-proxies" class="btn-danger btn-sm" title="Tự động loại bỏ các dòng proxy chết khỏi ô danh sách">
                    🗑️ Xóa ${deadItems.length} proxy lỗi
                  </button>
                ` : ''}
              </div>
          `;

          if (deadItems.length > 0) {
            html += `
              <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 6px; padding: 8px 10px;">
                <div style="color: #f87171; font-weight: 600; font-size: 11px; margin-bottom: 5px;">
                  ⚠️ Chi tiết các Proxy đang bị Lỗi / Không kết nối được:
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                  ${deadItems.map(d => {
                    let shortP = d.proxy;
                    const pParts = String(d.proxy || '').split(':');
                    if (pParts.length >= 2) shortP = `${pParts[0]}:${pParts[1]}`;
                    return `
                      <span style="background: rgba(0, 0, 0, 0.5); border: 1px solid #ef4444; color: #fca5a5; padding: 3px 8px; border-radius: 5px; font-family: monospace; font-size: 11px; display: inline-flex; align-items: center; gap: 6px;" title="${escapeHtml(d.proxy)}: ${escapeHtml(d.error || 'Timeout')}">
                        <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #ef4444;"></span>
                        <strong>${escapeHtml(shortP)}</strong>
                        <span style="color: #fca5a5; font-size: 10px;">(${escapeHtml(d.error || 'Timeout')})</span>
                      </span>
                    `;
                  }).join('')}
                </div>
              </div>
            `;
          }
          html += `</div>`;

          if (proxyCheckStatus) {
            proxyCheckStatus.innerHTML = html;
            const btnRemoveDead = document.getElementById('btn-remove-dead-proxies');
            if (btnRemoveDead) {
              btnRemoveDead.addEventListener('click', () => {
                const deadSet = new Set(deadItems.map(d => d.proxy));
                deadItems.forEach(d => {
                  const pParts = String(d.proxy || '').split(':');
                  if (pParts.length >= 2) deadSet.add(`${pParts[0]}:${pParts[1]}`);
                });

                const currentLines = textareaProxies.value.split('\n');
                const keptLines = currentLines.filter(line => {
                  const trimmed = line.trim();
                  if (!trimmed || trimmed.startsWith('#')) return true;
                  const parts = trimmed.split(':');
                  const short = parts.length >= 2 ? `${parts[0]}:${parts[1]}` : trimmed;
                  return !deadSet.has(trimmed) && !deadSet.has(short);
                });

                textareaProxies.value = keptLines.join('\n');
                safeStorageSet(STORAGE_KEY_PROXIES, textareaProxies.value);
                scheduleSaveProxiesToDb(true);
                proxyCheckCache.clear();
                aliveItems.forEach(r => {
                  proxyCheckCache.set(r.proxy, r);
                  const parts = String(r.proxy || '').split(':');
                  if (parts.length >= 2) proxyCheckCache.set(`${parts[0]}:${parts[1]}`, r);
                });
                updateProxyCountBadge();
                renderThreadProxyMapping();
                proxyCheckStatus.innerHTML = `<span style="color: #34d399; font-weight: 600;">✅ Đã loại bỏ ${deadItems.length} proxy lỗi và cập nhật CSDL. Hiện còn ${getValidProxyList().length} proxy sẵn sàng!</span>`;
                showToast(`Đã xóa ${deadItems.length} proxy lỗi & lưu CSDL!`, '✅');
              });
            }
          }
          showToast(`Kiểm tra xong: ${res.alive}/${res.total} proxy hoạt động${res.dead > 0 ? ` (${res.dead} lỗi)` : ''}`, res.alive > 0 ? '✅' : '⚠️');
        } else {
          if (proxyCheckStatus) {
            proxyCheckStatus.innerHTML = `<span style="color: #f87171;">❌ ${escapeHtml((res && res.message) || 'Lỗi kiểm tra proxy')}</span>`;
          }
        }
      } catch (err) {
        const errMsg = typeof err === 'string' ? err : (err && err.message ? err.message : JSON.stringify(err));
        if (proxyCheckStatus) {
          proxyCheckStatus.innerHTML = `<span style="color: #f87171;">❌ ${escapeHtml(errMsg || 'Lỗi kiểm tra proxy')}</span>`;
        }
      } finally {
        btnCheckProxies.disabled = false;
      }
    });
  }
}

// ================= Server Dropdown & Persistence =================
const STORAGE_KEY_ZONE = 'pokemon_master_saved_zone';

async function loadServers() {
  allServers = await window.electronAPI.getServers();
  if (!Array.isArray(allServers)) allServers = [];
  renderServerOptions();

  if (lblSelectServer && allServers.length > 0) {
    lblSelectServer.textContent = `Chọn Máy Chủ (${allServers.length.toLocaleString('en-US')} Server):`;
  }

  const savedZone = safeStorageGet(STORAGE_KEY_ZONE);
  const defaultZone = allServers.length > 0 ? String(allServers[0].id) : '2160';
  setServerSelection(savedZone || defaultZone);
}

function renderServerOptions(filterText = '') {
  if (!selectServer) return;
  const currentVal = selectServer.value;
  selectServer.innerHTML = '';

  const maxZoneId = allServers.length > 0 ? Math.max(...allServers.map(s => parseInt(s.id, 10) || 0)) : 2160;
  const filter = filterText.trim().toLowerCase();
  const filtered = allServers.filter(s => {
    if (!filter) return true;
    return String(s.name || '').toLowerCase().includes(filter) ||
           String(s.id || '').toLowerCase().includes(filter) ||
           String(s.tcp || '').toLowerCase().includes(filter);
  });

  if (filtered.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = allServers.length === 0
      ? '⚠️ Chưa có server (bấm 🔄 để tải)'
      : '❌ Không tìm thấy server phù hợp';
    selectServer.appendChild(opt);
    return;
  }

  filtered.forEach(s => {
    const opt = document.createElement('option');
    opt.value = String(s.id);
    const isNewest = parseInt(s.id, 10) === maxZoneId;
    const cleanName = String(s.name || `Server ${s.id}`).replace('Poke ', '');
    const tag = isNewest ? `🔥 ${cleanName} (Mới)` : cleanName;
    opt.textContent = `${tag} • Zone ${s.id}`;
    opt.dataset.tcp = s.tcp || '';
    opt.dataset.name = s.name || '';
    selectServer.appendChild(opt);
  });

  if (currentVal && filtered.some(s => String(s.id) === String(currentVal))) {
    selectServer.value = currentVal;
  }
}

if (window.electronAPI.onServersUpdated) {
  window.electronAPI.onServersUpdated((payload) => {
    const servers = payload && payload.servers ? payload.servers : [];
    const isNew = Boolean(payload && payload.isNew);
    const count = (payload && payload.count) || servers.length;
    if (servers.length > 0) {
      allServers = servers;
      renderServerOptions(inputSearchServer ? inputSearchServer.value : '');
      if (lblSelectServer) {
        lblSelectServer.textContent = `Chọn Máy Chủ (${allServers.length.toLocaleString('en-US')} Server):`;
      }
      if (inputZone && inputZone.value) {
        setServerSelection(inputZone.value);
      }
      if (isNew) {
        showToast(`Đã tự động cập nhật: Tổng ${count} Server trực tuyến!`, '⚡');
      }
    }
  });
}

if (btnRefreshServers) {
  btnRefreshServers.addEventListener('click', async () => {
    btnRefreshServers.classList.add('spinning');
    try {
      const res = await window.electronAPI.refreshServers();
      if (res && res.success && Array.isArray(res.servers)) {
        allServers = res.servers;
        renderServerOptions(inputSearchServer ? inputSearchServer.value : '');
        if (lblSelectServer) {
          lblSelectServer.textContent = `Chọn Máy Chủ (${(res.count || res.servers.length).toLocaleString('en-US')} Server):`;
        }
        if (inputZone && inputZone.value) {
          setServerSelection(inputZone.value);
        }
        showToast(`Đã làm mới: ${res.count || res.servers.length} Server trực tuyến!`, '🔄');
      } else {
        showToast((res && res.message) || 'Không thể kết nối đến máy chủ game', '⚠️');
      }
    } catch (_e) {
      showToast('Lỗi khi làm mới danh sách máy chủ', '❌');
    } finally {
      setTimeout(() => btnRefreshServers.classList.remove('spinning'), 600);
    }
  });
}

function setServerSelection(zoneId) {
  const target = allServers.find(s => String(s.id) === String(zoneId)) || allServers[0];
  if (target) {
    if (selectServer) selectServer.value = String(target.id);
    if (inputZone) inputZone.value = String(target.id);
    if (badgeZoneId) badgeZoneId.textContent = `Zone ${target.id}`;
    if (endpointText) endpointText.textContent = `TCP Socket: ${target.tcp || 'N/A'}`;
    safeStorageSet(STORAGE_KEY_ZONE, target.id);
  }
}

if (selectServer) {
  selectServer.addEventListener('change', () => {
    const selectedId = selectServer.value;
    const s = allServers.find(srv => String(srv.id) === String(selectedId));
    if (s) {
      if (inputZone) inputZone.value = String(s.id);
      if (badgeZoneId) badgeZoneId.textContent = `Zone ${s.id}`;
      if (endpointText) endpointText.textContent = `TCP Socket: ${s.tcp || 'N/A'}`;
      safeStorageSet(STORAGE_KEY_ZONE, s.id);
      showToast(`Đã chọn: ${s.name} (Zone ${s.id})`, '🌐');
    }
  });
}

if (inputSearchServer) {
  inputSearchServer.addEventListener('input', () => {
    renderServerOptions(inputSearchServer.value);
    const firstOpt = selectServer ? selectServer.querySelector('option') : null;
    if (firstOpt && firstOpt.value) {
      selectServer.value = firstOpt.value;
      const s = allServers.find(srv => String(srv.id) === String(firstOpt.value));
      if (s) {
        if (inputZone) inputZone.value = String(s.id);
        if (badgeZoneId) badgeZoneId.textContent = `Zone ${s.id}`;
        if (endpointText) endpointText.textContent = `TCP Socket: ${s.tcp || 'N/A'}`;
        safeStorageSet(STORAGE_KEY_ZONE, s.id);
      }
    }
  });
}

// ================= Count Slider sync =================
if (inputCountRange && inputCount && countDisplay) {
  inputCountRange.addEventListener('input', () => {
    inputCount.value = inputCountRange.value;
    countDisplay.textContent = inputCountRange.value;
    safeStorageSet('pokemon_master_count', inputCountRange.value);
  });

  inputCount.addEventListener('input', () => {
    const v = Math.max(1, parseInt(inputCount.value, 10) || 1);
    inputCountRange.value = Math.min(v, parseInt(inputCountRange.max, 10) || 100);
    countDisplay.textContent = String(v);
    safeStorageSet('pokemon_master_count', v);
  });
}

// ================= Tab Navigation =================
let currentActiveTab = 'tab-settings';

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tabButtons.forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false');
    });
    tabContents.forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');
    currentActiveTab = btn.dataset.tab;
    const target = document.getElementById(currentActiveTab);
    if (target) target.classList.add('active');

    closeExportDropdown();

    if (currentActiveTab === 'tab-accounts') {
      renderAccountsTable();
    } else if (currentActiveTab === 'tab-inventory') {
      renderPetCollection();
    } else if (currentActiveTab === 'tab-errors') {
      renderErrorsTable();
    } else if (currentActiveTab === 'tab-console') {
      if (chkAutoscroll && chkAutoscroll.checked && consoleLogs) {
        requestAnimationFrame(() => {
          consoleLogs.scrollTop = consoleLogs.scrollHeight;
        });
      }
    }
  });
});

// ================= Console Filtering =================
filterButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    filterButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentLogFilter = btn.dataset.filter;
    applyLogFilter();
  });
});

function applyLogFilter() {
  if (!consoleLogs) return;
  const lines = consoleLogs.querySelectorAll('.log-line');
  lines.forEach(line => {
    if (currentLogFilter === 'all') {
      line.style.display = 'flex';
    } else {
      line.style.display = line.classList.contains(currentLogFilter) ? 'flex' : 'none';
    }
  });
}

if (btnClearConsole && consoleLogs) {
  btnClearConsole.addEventListener('click', () => {
    consoleLogs.innerHTML = '';
  });
}

// ================= Toast Message =================
function showToast(message, icon = '✅') {
  if (!toastContainer) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  const iconSpan = document.createElement('span');
  iconSpan.textContent = icon;
  const msgSpan = document.createElement('span');
  msgSpan.textContent = String(message ?? '');
  toast.appendChild(iconSpan);
  toast.appendChild(msgSpan);
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 280);
  }, 2400);
}
window.showWebToast = showToast;

// ================= Add Log Line & Smooth Scroll Management =================
if (chkAutoscroll) {
  chkAutoscroll.addEventListener('change', () => {
    if (chkAutoscroll.checked && consoleLogs) {
      consoleLogs.scrollTop = consoleLogs.scrollHeight;
    }
  });
}

function requestLogScroll() {
  if (chkAutoscroll && chkAutoscroll.checked && consoleLogs) {
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
  }
}

function addLogLine(text, type = 'normal', time = null) {
  if (!consoleLogs) return;
  const timeStr = time || new Date().toLocaleTimeString();
  const line = document.createElement('div');
  line.className = `log-line ${type}`;

  let badgeText = 'INFO';
  let badgeClass = 'badge-normal';
  if (type === 'pet') {
    badgeText = 'PET';
    badgeClass = 'badge-pet';
  } else if (type === 'gacha') {
    badgeText = 'GACHA';
    badgeClass = 'badge-gacha';
  } else if (type === 'mail') {
    badgeText = 'MAIL';
    badgeClass = 'badge-mail';
  } else if (type === 'success') {
    badgeText = 'SUCCESS';
    badgeClass = 'badge-success';
  } else if (type === 'warning') {
    badgeText = 'ALERT';
    badgeClass = 'badge-warning';
  }

  line.innerHTML = `
    <span class="log-time">${escapeHtml(timeStr)}</span>
    <span class="log-badge ${badgeClass}">${badgeText}</span>
    <span class="log-text">${escapeHtml(text)}</span>
  `;

  if (currentLogFilter !== 'all' && type !== currentLogFilter) {
    line.style.display = 'none';
  }

  consoleLogs.appendChild(line);

  while (consoleLogs.children.length > 250) {
    consoleLogs.removeChild(consoleLogs.firstChild);
  }

  requestLogScroll();
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ================= Target Pet Filter Logic =================
function renderSelectedPetChips() {
  if (!selectedPetsContainer) return;
  selectedPetsContainer.innerHTML = '';
  if (selectedPetSet.size === 0) {
    selectedPetsContainer.innerHTML = `<span style="font-size: 11.5px; color: var(--text-dim); padding-left: 4px;">Chưa chọn Pet (giữ lại tất cả nick)</span>`;
    return;
  }

  selectedPetSet.forEach(petName => {
    const isLeg = LEGENDARY_PETS.has(petName);
    const chip = document.createElement('span');
    chip.className = `selected-pet-chip ${isLeg ? 'legendary' : ''}`;
    const icon = isLeg ? '🌟' : '⚡';
    chip.innerHTML = `
      <span>${icon} ${escapeHtml(petName)}</span>
      <span class="chip-remove-btn" data-remove="${escapeHtml(petName)}" title="Bỏ chọn">✕</span>
    `;
    selectedPetsContainer.appendChild(chip);
  });

  selectedPetsContainer.querySelectorAll('.chip-remove-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const pet = btn.dataset.remove;
      selectedPetSet.delete(pet);
      saveSelectedPets();
      renderSelectedPetChips();
      updateQuickTagsActive();
      currentAccPage = 1;
      renderAccountsTable({ resetScroll: true });
    });
  });
}

function saveSelectedPets() {
  safeStorageSet('pokemon_master_selected_pets', JSON.stringify([...selectedPetSet]));
}

function updateQuickTagsActive() {
  quickTags.forEach(tag => {
    if (selectedPetSet.has(tag.dataset.pet)) {
      tag.classList.add('active');
    } else {
      tag.classList.remove('active');
    }
  });
}

quickTags.forEach(tag => {
  tag.addEventListener('click', () => {
    const pet = tag.dataset.pet;
    if (selectedPetSet.has(pet)) {
      selectedPetSet.delete(pet);
    } else {
      selectedPetSet.add(pet);
    }
    saveSelectedPets();
    renderSelectedPetChips();
    updateQuickTagsActive();
    currentAccPage = 1;
    renderAccountsTable({ resetScroll: true });
  });
});

function showPetSuggestions(query) {
  if (!petSuggestions) return;
  if (!query || !query.trim()) {
    petSuggestions.classList.remove('open');
    petSuggestions.innerHTML = '';
    return;
  }

  const q = query.trim().toLowerCase();
  const pokedex = fullPokedex || [];
  const matches = pokedex.filter(p => String(p.name || '').toLowerCase().includes(q)).slice(0, 10);

  if (matches.length === 0) {
    petSuggestions.innerHTML = `<div style="padding: 10px; text-align: center; color: var(--text-dim); font-size: 12px;">Không tìm thấy Pokémon nào</div>`;
    petSuggestions.classList.add('open');
    return;
  }

  petSuggestions.innerHTML = '';
  matches.forEach(item => {
    const div = document.createElement('div');
    div.className = 'suggestion-item';
    let tierTag = '<span class="tag-tier-common">Phổ thông</span>';
    if (item.tier === 'legendary') tierTag = '<span class="tag-tier-legendary">🌟 Thần Thú</span>';
    else if (item.tier === 'rare') tierTag = '<span class="tag-tier-rare">💎 Hiếm</span>';
    else if (item.tier === 'starter') tierTag = '<span class="tag-tier-starter">🌱 Starter</span>';

    div.innerHTML = `
      <span class="suggestion-name">${escapeHtml(item.name)}</span>
      <div class="suggestion-meta">
        ${tierTag}
        <span style="color: var(--text-dim); font-size: 10px;">${escapeHtml(item.type || '')}</span>
      </div>
    `;

    div.addEventListener('click', () => {
      selectedPetSet.add(item.name);
      saveSelectedPets();
      renderSelectedPetChips();
      updateQuickTagsActive();
      currentAccPage = 1;
      renderAccountsTable({ resetScroll: true });
      if (inputTargetPet) inputTargetPet.value = '';
      petSuggestions.classList.remove('open');
      showToast(`Đã thêm: ${item.name}`, '🎯');
    });

    petSuggestions.appendChild(div);
  });

  petSuggestions.classList.add('open');
}

if (inputTargetPet) {
  inputTargetPet.addEventListener('input', () => {
    showPetSuggestions(inputTargetPet.value);
  });

  inputTargetPet.addEventListener('focus', () => {
    if (inputTargetPet.value.trim()) {
      showPetSuggestions(inputTargetPet.value);
    }
  });
}

if (btnClearTargetInput) {
  btnClearTargetInput.addEventListener('click', () => {
    if (inputTargetPet) inputTargetPet.value = '';
    if (petSuggestions) petSuggestions.classList.remove('open');
  });
}

document.addEventListener('click', (e) => {
  if (petSuggestions && !e.target.closest('.pet-search-wrapper')) {
    petSuggestions.classList.remove('open');
  }
});

function setPetFilterMode(mode) {
  targetFilterMode = mode;
  safeStorageSet('pokemon_master_filter_mode', mode);

  if (mode === 'legendary') {
    if (btnModeLegendary) btnModeLegendary.classList.add('active');
    if (btnModeCustom) btnModeCustom.classList.remove('active');
    if (customPetControls) customPetControls.style.display = 'none';
    if (legendaryModeBox) legendaryModeBox.style.display = 'block';
    if (boxMatchAllPets) boxMatchAllPets.style.display = 'none';
  } else {
    if (btnModeCustom) btnModeCustom.classList.add('active');
    if (btnModeLegendary) btnModeLegendary.classList.remove('active');
    if (customPetControls) customPetControls.style.display = 'block';
    if (legendaryModeBox) legendaryModeBox.style.display = 'none';
    if (boxMatchAllPets) boxMatchAllPets.style.display = 'block';
  }
  currentAccPage = 1;
  renderAccountsTable({ resetScroll: true });
}

if (btnModeCustom) btnModeCustom.addEventListener('click', () => setPetFilterMode('custom'));
if (btnModeLegendary) btnModeLegendary.addEventListener('click', () => setPetFilterMode('legendary'));

const savedMatchAll = safeStorageGet(STORAGE_KEY_MATCH_ALL_PETS);
if (savedMatchAll !== null && chkMatchAllPets) {
  chkMatchAllPets.checked = (savedMatchAll === 'true');
}

if (chkMatchAllPets) {
  chkMatchAllPets.addEventListener('change', () => {
    safeStorageSet(STORAGE_KEY_MATCH_ALL_PETS, chkMatchAllPets.checked);
    currentAccPage = 1;
    renderAccountsTable({ resetScroll: true });
  });
}

// Restore filter-only-targets & nature filter
const savedFilterOnlyTargets = safeStorageGet('pokemon_master_filter_only_targets');
if (savedFilterOnlyTargets !== null && chkFilterOnlyTargets) {
  chkFilterOnlyTargets.checked = savedFilterOnlyTargets === 'true';
  currentAccFilter = chkFilterOnlyTargets.checked ? 'target' : 'all';
}

const savedNatureFilter = safeStorageGet('pokemon_master_nature_filter');
if (savedNatureFilter && selectNatureFilter) {
  selectNatureFilter.value = savedNatureFilter;
}

// Init filter states
setPetFilterMode(targetFilterMode);
renderSelectedPetChips();
updateQuickTagsActive();
updatePillStyles();

if (chkFilterOnlyTargets) {
  chkFilterOnlyTargets.addEventListener('change', () => {
    safeStorageSet('pokemon_master_filter_only_targets', chkFilterOnlyTargets.checked);
    currentAccFilter = chkFilterOnlyTargets.checked ? 'target' : 'all';
    updatePillStyles();
    currentAccPage = 1;
    renderAccountsTable({ resetScroll: true });
  });
}

accPills.forEach(pill => {
  pill.addEventListener('click', () => {
    currentAccFilter = pill.dataset.accfilter;
    updatePillStyles();
    if (chkFilterOnlyTargets) {
      chkFilterOnlyTargets.checked = (currentAccFilter === 'target');
      safeStorageSet('pokemon_master_filter_only_targets', chkFilterOnlyTargets.checked);
    }
    currentAccPage = 1;
    renderAccountsTable({ resetScroll: true });
  });
});

function updatePillStyles() {
  accPills.forEach(p => {
    if (p.dataset.accfilter === currentAccFilter) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });
}

function checkAccountTargetHit(acc) {
  const rawPets = acc.pets || [];
  const parsedPets = rawPets.map(parsePetEntry);
  const selectedNatureFilter = selectNatureFilter ? selectNatureFilter.value : 'all';

  function matchesNature(pObj) {
    if (selectedNatureFilter === 'all') return true;
    if (!pObj.nature) return false;
    if (selectedNatureFilter === 'meta') return !!pObj.nature.meta;
    if (/^\d+$/.test(selectedNatureFilter)) {
      return pObj.natureId === parseInt(selectedNatureFilter, 10);
    }
    return pObj.nature.type === selectedNatureFilter ||
           (pObj.nature.name && pObj.nature.name.toLowerCase() === selectedNatureFilter.toLowerCase());
  }

  let petIsHit = false;
  let hitObjects = [];
  let hitPets = [];
  let isCombo = false;

  if (targetFilterMode === 'legendary') {
    hitObjects = parsedPets.filter(p => LEGENDARY_PETS.has(p.name) && matchesNature(p));
    hitPets = hitObjects.map(p => p.name);
    petIsHit = hitPets.length > 0;
  } else if (selectedPetSet.size > 0) {
    const matchAll = chkMatchAllPets ? chkMatchAllPets.checked : false;
    const targets = [...selectedPetSet];

    if (matchAll && targets.length > 1) {
      isCombo = true;
      const hasAllTargets = targets.every(t =>
        parsedPets.some(p => p.name.toLowerCase() === t.toLowerCase() && matchesNature(p))
      );

      if (hasAllTargets) {
        hitObjects = parsedPets.filter(p =>
          targets.some(t => t.toLowerCase() === p.name.toLowerCase()) && matchesNature(p)
        );
        hitPets = hitObjects.map(p => p.name);
        petIsHit = true;
      } else {
        hitObjects = [];
        hitPets = [];
        petIsHit = false;
      }
    } else {
      hitObjects = parsedPets.filter(p => targets.some(t => t.toLowerCase() === p.name.toLowerCase()) && matchesNature(p));
      hitPets = hitObjects.map(p => p.name);
      petIsHit = hitPets.length > 0;
    }
  } else {
    hitObjects = parsedPets.filter(matchesNature);
    hitPets = hitObjects.map(p => p.name);
    petIsHit = (selectedNatureFilter === 'all' || hitPets.length > 0);
  }

  return {
    isHit: petIsHit,
    hitPets,
    hitObjects,
    hitItems: [],
    itemIsHit: false,
    petIsHit,
    isCombo
  };
}

// ================= Task Execution =================
if (btnStart) {
  btnStart.addEventListener('click', async () => {
    if (isRunning) return;

    const count = parseInt(inputCount.value, 10) || 1;
    const zone = inputZone.value.trim() || '2160';
    const delayMin = parseFloat(inputDelayMin.value) || 1.5;
    const delayMax = parseFloat(inputDelayMax.value) || 3.0;
    const isCombo = (chkMatchAllPets && chkMatchAllPets.checked && selectedPetSet.size > 1);
    const targetDesc = targetFilterMode === 'legendary'
      ? 'Mọi Thần Thú'
      : (selectedPetSet.size > 0
          ? (isCombo ? `Combo ĐỦ: ${[...selectedPetSet].join(' + ')}` : [...selectedPetSet].join(', '))
          : 'Tất cả Pet');

    const maxPerMinute = inputRateLimit ? (parseInt(inputRateLimit.value, 10) || 100) : 100;

    const isRandomUser = chkRandomUsername ? chkRandomUsername.checked : true;
    const customUsername = (!isRandomUser && inputCustomUsername) ? inputCustomUsername.value.trim() : null;

    const isRandomPass = chkRandomPassword ? chkRandomPassword.checked : true;
    const customPassword = (!isRandomPass && inputCustomPassword) ? inputCustomPassword.value.trim() : null;

    if (!isRandomUser && !customUsername) {
      showToast('Vui lòng nhập Username cố định hoặc tick Random!', '⚠️');
      if (inputCustomUsername) inputCustomUsername.focus();
      return;
    }
    if (!isRandomPass && !customPassword) {
      showToast('Vui lòng nhập Mật khẩu cố định hoặc tick Random!', '⚠️');
      if (inputCustomPassword) inputCustomPassword.focus();
      return;
    }

    const threads = inputThreads ? (parseInt(inputThreads.value, 10) || 1) : 1;
    const isProxyMode = radioNetProxy && radioNetProxy.checked;
    const networkMode = isProxyMode ? 'proxy' : 'direct';
    const proxyType = selectProxyType ? selectProxyType.value : 'socks5';
    const proxiesText = textareaProxies ? textareaProxies.value : '';

    if (isProxyMode) {
      const validLines = proxiesText.split('\n').map(l => l.trim()).filter(l => l.length > 0 && !l.startsWith('#'));
      if (validLines.length === 0) {
        showToast('Bạn đang chọn chế độ Proxy nhưng chưa dán danh sách Proxy!', '⚠️');
        if (textareaProxies) textareaProxies.focus();
        return;
      }
    }

    const autoIncrementUsername = chkAutoIncrementUsername ? chkAutoIncrementUsername.checked : true;
    const config = {
      count,
      zone,
      delayMin,
      delayMax,
      maxPerMinute,
      visitorUpgrade: true,
      claimMail: true,
      autoDraw: true,
      customUsername,
      customPassword,
      autoIncrementUsername,
      threads,
      networkMode,
      proxyType,
      proxies: proxiesText
    };

    setRunningState(true, 'normal');
    const incDesc = (!isRandomUser && autoIncrementUsername) ? ' (Tự tăng số)' : '';
    const userDesc = customUsername ? `TK: '${customUsername}'${incDesc}` : 'TK: Random';
    const passDesc = customPassword ? 'MK: Cố định' : 'MK: Random';
    const netDesc = isProxyMode ? `Proxy: ${proxyType.toUpperCase()}` : 'Mạng gốc';
    addLogLine(`🚀 Bắt đầu tạo ${count} tài khoản trên Server ${zone} (${threads} luồng, ${netDesc}, ${userDesc}, ${passDesc}, Mục tiêu: [${targetDesc}])...`, 'success');

    const tabConsoleBtn = document.querySelector('.tab-btn[data-tab="tab-console"]');
    if (tabConsoleBtn) tabConsoleBtn.click();

    const res = await window.electronAPI.startTask(config);
    if (!res || !res.success) {
      addLogLine(`❌ Không thể khởi động: ${(res && res.message) || 'Lỗi không xác định'}`, 'warning');
      showToast((res && res.message) || 'Không thể khởi động tiến trình', '⚠️');
      setRunningState(false);
    }
  });
}

if (btnStop) {
  btnStop.addEventListener('click', async () => {
    if (!isRunning) return;
    addLogLine('⏹️ Đang gửi tín hiệu dừng tiến trình...', 'warning');
    await window.electronAPI.stopTask();
    setRunningState(false);
  });
}

let currentTaskMode = 'normal';

function setRunningState(running, mode = 'normal') {
  isRunning = Boolean(running);
  currentTaskMode = isRunning ? mode : 'normal';

  if (btnStart) btnStart.disabled = isRunning;
  if (btnStop) btnStop.disabled = !isRunning;

  if (statusIndicator) {
    statusIndicator.className = isRunning ? 'status-indicator running' : 'status-indicator';
  }
  if (statusText) {
    statusText.textContent = isRunning
      ? (currentTaskMode === 'resume' ? 'Đang chạy tiếp nhận vé...' : 'Đang chạy tự động...')
      : 'Hệ thống sẵn sàng';
  }

  const headerTaskBadge = document.getElementById('header-task-badge');
  const headerTaskText = document.getElementById('header-task-text');
  if (headerTaskBadge) {
    headerTaskBadge.classList.toggle('task-running', isRunning);
  }
  if (headerTaskText) {
    headerTaskText.textContent = isRunning
      ? (currentTaskMode === 'resume' ? 'Đang chạy tiếp' : 'Đang chạy')
      : 'Sẵn sàng';
  }

  if (btnResumePending) {
    if (isRunning && currentTaskMode === 'resume') {
      btnResumePending.className = 'btn-danger btn-sm';
      btnResumePending.innerHTML = '⏹️ Dừng chạy tiếp';
    } else {
      btnResumePending.className = 'btn-warning btn-sm';
      const pendingCount = accountsList.filter(a => a.status === 'pending_reward' || a.status === 'pending_draw').length;
      btnResumePending.innerHTML = `⚡ Tiếp tục nhận vé (<span id="count-resume-pending">${pendingCount}</span>)`;
      btnResumePending.style.display = pendingCount > 0 ? 'inline-flex' : 'none';
    }
  }
}

// ================= Accounts Table & Pet Collection =================
let isReloadingAccounts = false;
let pendingReloadTimer = null;

async function reloadAccounts(forceRender = false) {
  if (isReloadingAccounts) return;
  isReloadingAccounts = true;
  try {
    const data = await window.electronAPI.getAccounts();
    accountsList = Array.isArray(data) ? data : [];
    updateMetrics();
    renderAccountsTable();
    if (forceRender || currentActiveTab === 'tab-inventory') {
      renderPetCollection();
    }
  } catch (err) {
    console.error('Lỗi nạp accounts:', err);
  } finally {
    isReloadingAccounts = false;
  }
}

function buildPaginationPagesList(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages = [1];
  const left = Math.max(2, current - 1);
  const right = Math.min(total - 1, current + 1);

  if (left > 2) pages.push('...');
  for (let p = left; p <= right; p++) {
    pages.push(p);
  }
  if (right < total - 1) pages.push('...');
  pages.push(total);
  return pages;
}

function updateAccountsPaginationBar(totalItems, totalPages, startIdx, pageCount) {
  if (accPaginationInfo) {
    if (totalItems === 0) {
      accPaginationInfo.innerHTML = 'Hiển thị <strong>0</strong> tài khoản';
    } else {
      const fromNum = (startIdx + 1).toLocaleString('en-US');
      const toNum = (startIdx + pageCount).toLocaleString('en-US');
      const totalStr = totalItems.toLocaleString('en-US');
      accPaginationInfo.innerHTML = `Hiển thị <strong>${fromNum}–${toNum}</strong> / <strong>${totalStr}</strong> tài khoản <span style="color: var(--text-dim);">• Trang ${currentAccPage}/${totalPages}</span>`;
    }
  }

  const isFirst = currentAccPage <= 1 || totalItems === 0;
  const isLast = currentAccPage >= totalPages || totalItems === 0;
  if (btnAccPageFirst) btnAccPageFirst.disabled = isFirst;
  if (btnAccPagePrev) btnAccPagePrev.disabled = isFirst;
  if (btnAccPageNext) btnAccPageNext.disabled = isLast;
  if (btnAccPageLast) btnAccPageLast.disabled = isLast;

  if (accPaginationPages) {
    if (totalItems === 0) {
      accPaginationPages.innerHTML = `<button type="button" class="pagination-btn active" disabled>1</button>`;
      return;
    }
    const pageTokens = buildPaginationPagesList(currentAccPage, totalPages);
    accPaginationPages.innerHTML = pageTokens.map(token => {
      if (token === '...') {
        return `<span class="pagination-ellipsis">…</span>`;
      }
      const activeCls = token === currentAccPage ? ' active' : '';
      return `<button type="button" class="pagination-btn page-num-btn${activeCls}" data-page="${token}">${token}</button>`;
    }).join('');
  }
}

function renderAccountsTable(options = {}) {
  if (!accountsTbody) return;
  const { resetScroll = false } = options;
  const filter = inputSearchAcc ? inputSearchAcc.value.trim().toLowerCase() : '';
  accountsTbody.innerHTML = '';

  let hitCount = 0;
  let missCount = 0;
  let pendingCount = 0;
  const matchedEntries = [];
  currentFilteredAccounts = [];

  for (let i = 0; i < accountsList.length; i++) {
    const acc = accountsList[i];
    const isPending = acc.status === 'pending_reward' || acc.status === 'pending_draw';
    let hitInfo = null;

    if (isPending) {
      pendingCount++;
    } else {
      hitInfo = checkAccountTargetHit(acc);
      if (hitInfo.isHit) hitCount++;
      else missCount++;
    }

    let matchesCategory = false;
    if (currentAccFilter === 'all') {
      matchesCategory = true;
    } else if (currentAccFilter === 'pending') {
      matchesCategory = isPending;
    } else if (isPending) {
      matchesCategory = false;
    } else if (currentAccFilter === 'miss') {
      matchesCategory = !hitInfo.isHit;
    } else {
      matchesCategory = hitInfo.isHit;
    }

    if (!matchesCategory) continue;

    if (filter) {
      const uMatch = String(acc.username || '').toLowerCase().includes(filter) ||
                     String(acc.character_name || '').toLowerCase().includes(filter) ||
                     String(acc.zone_id || '').toLowerCase().includes(filter) ||
                     String(acc.user_id || '').toLowerCase().includes(filter) ||
                     String(acc.lucky_sigh || '').toLowerCase().includes(filter);
      let petMatch = false;
      if (!uMatch && acc.pets && acc.pets.length > 0) {
        petMatch = acc.pets.some(p => {
          const pet = parsePetEntry(p);
          const natName = pet.nature ? pet.nature.name.toLowerCase() : '';
          const natEn = pet.nature ? pet.nature.en.toLowerCase() : '';
          return pet.name.toLowerCase().includes(filter) || natName.includes(filter) || natEn.includes(filter);
        });
      }
      if (!uMatch && !petMatch) continue;
    }

    currentFilteredAccounts.push(acc);
    matchedEntries.push({ acc, isPending, hitInfo });
  }

  if (countTargetHits) countTargetHits.textContent = hitCount;
  if (countTargetMiss) countTargetMiss.textContent = missCount;
  if (countTargetPending) countTargetPending.textContent = pendingCount;
  if (countResumePending && (!isRunning || currentTaskMode !== 'resume')) countResumePending.textContent = pendingCount;
  if (btnResumePending) {
    if (isRunning && currentTaskMode === 'resume') {
      btnResumePending.style.display = 'inline-flex';
      btnResumePending.className = 'btn-danger btn-sm';
      btnResumePending.innerHTML = '⏹️ Dừng chạy tiếp';
    } else {
      btnResumePending.style.display = pendingCount > 0 ? 'inline-flex' : 'none';
      btnResumePending.className = 'btn-warning btn-sm';
      btnResumePending.innerHTML = `⚡ Tiếp tục nhận vé (<span id="count-resume-pending">${pendingCount}</span>)`;
    }
  }

  updateSmartDeleteButton();

  const totalItems = matchedEntries.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / accPageSize));
  if (currentAccPage > totalPages) currentAccPage = totalPages;
  if (currentAccPage < 1) currentAccPage = 1;

  if (totalItems === 0) {
    updateAccountsPaginationBar(0, 1, 0, 0);
    const emptyMsg = currentAccFilter === 'target'
      ? 'Chưa có tài khoản nào quay trúng Pet mục tiêu đang chọn.'
      : (currentAccFilter === 'pending'
          ? 'Không có tài khoản nào đang chờ nhận vé hoặc rút pet.'
          : 'Không tìm thấy tài khoản phù hợp.');
    accountsTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-dim); padding: 28px;">${emptyMsg}</td></tr>`;
    return;
  }

  const startIdx = (currentAccPage - 1) * accPageSize;
  const pageEntries = matchedEntries.slice(startIdx, startIdx + accPageSize);
  updateAccountsPaginationBar(totalItems, totalPages, startIdx, pageEntries.length);

  const fragment = document.createDocumentFragment();

  pageEntries.forEach(({ acc, isPending, hitInfo }, idx) => {
    const tr = document.createElement('tr');
    const resolvedHit = hitInfo || { isHit: false, hitPets: [], hitObjects: [], isCombo: false };
    const { isHit, hitPets, hitObjects, isCombo } = resolvedHit;
    const hitPetSet = hitPets.length > 0 ? new Set(hitPets) : null;

    let resultBadge = '';
    if (acc.status === 'pending_reward') {
      resultBadge = `<span class="badge-target-pending" style="background: rgba(234, 179, 8, 0.15); color: #f59e0b; border: 1px solid rgba(234, 179, 8, 0.35); padding: 3px 8px; border-radius: 5px; font-size: 11px; font-weight: 700;">⏳ Chờ nhận vé (B5)</span>`;
    } else if (acc.status === 'pending_draw') {
      resultBadge = `<span class="badge-target-pending" style="background: rgba(234, 179, 8, 0.15); color: #f59e0b; border: 1px solid rgba(234, 179, 8, 0.35); padding: 3px 8px; border-radius: 5px; font-size: 11px; font-weight: 700;">⏳ Chờ rút pet (B6)</span>`;
    } else if (!acc.pets || acc.pets.length === 0) {
      resultBadge = `<span class="badge-target-pending" style="background: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.35); padding: 3px 8px; border-radius: 5px; font-size: 11px;">⏳ Đang tạo/chờ ấp</span>`;
    } else if (isHit) {
      const parts = [];
      const safeHitObjs = (Array.isArray(hitObjects) && hitObjects.length > 0) ? hitObjects : (hitPets || []).map(p => ({ name: p, nature: null }));
      if (resolvedHit.petIsHit && safeHitObjs.length > 0) {
        const petDetailsHtml = safeHitObjs.map(pObj => {
          if (pObj.nature) {
            const nat = pObj.nature;
            const pillTypeClass = nat.meta ? 'meta-s' : `type-${nat.type}`;
            const buffDesc = nat.buff ? `${nat.buff} ${nat.nerf}`.trim() : 'Cân bằng (+0%)';
            const tooltipData = `data-nature-title="${escapeHtml(nat.name)} (${escapeHtml(nat.en)})" data-nature-buff="${escapeHtml(buffDesc)}" data-nature-desc="${escapeHtml(nat.desc)}"`;
            return `<span class="target-name-with-nature">${escapeHtml(pObj.name)} <span class="nature-pill ${pillTypeClass}" ${tooltipData}>${escapeHtml(nat.name)}</span></span>`;
          } else {
            const tooltipData = `data-nature-title="${escapeHtml(pObj.name)}" data-nature-buff="Chưa có dữ liệu tính cách" data-nature-desc="Tài khoản này chưa có dữ liệu tính cách. Hãy bấm Đồng bộ hoặc tạo nick mới."`;
            return `<span class="target-name-with-nature has-nature-tooltip" ${tooltipData} style="cursor: pointer;">${escapeHtml(pObj.name)}</span>`;
          }
        }).join(', ');
        parts.push(petDetailsHtml);
      }

      if (resolvedHit.itemIsHit) {
        const hitItemLabels = (resolvedHit.hitItems && resolvedHit.hitItems.length > 0)
          ? resolvedHit.hitItems.map(it => escapeHtml(it)).join(', ')
          : escapeHtml(acc.lucky_sigh || 'Quẻ');
        parts.push(`<span class="lucky-item-badge" style="color: #fda4af; font-weight: 700;">🎋 ${hitItemLabels}</span>`);
      }

      const hitDetailsHtml = parts.join(' | ') || (hitPets.length > 0 ? hitPets.map(escapeHtml).join(', ') : 'Mục tiêu');
      const label = isCombo ? `🎯 COMBO (${hitDetailsHtml})` : `🎯 ĐẠT (${hitDetailsHtml})`;
      resultBadge = `<span class="badge-target-hit">${label}</span>`;
    } else {
      resultBadge = `<span class="badge-target-miss">❌ Trượt</span>`;
    }

    const petChipsHtml = (acc.pets || []).map(petRaw => {
      const pet = parsePetEntry(petRaw);
      const isLegendary = LEGENDARY_PETS.has(pet.name);
      const isRare = RARE_PETS.has(pet.name);
      const isTarget = hitPetSet ? hitPetSet.has(pet.name) : false;
      const cls = isTarget
        ? 'pet-chip legendary has-nature'
        : (isLegendary ? 'pet-chip legendary has-nature' : (isRare ? 'pet-chip rare' : 'pet-chip'));
      const icon = isTarget ? '🎯 ' : (isLegendary ? '🌟 ' : '');

      let natureBadgeHtml = '';
      let chipTooltip = '';
      if (pet.nature) {
        const nat = pet.nature;
        const pillTypeClass = nat.meta ? 'meta-s' : `type-${nat.type}`;
        const buffDesc = nat.buff ? `${nat.buff} ${nat.nerf}`.trim() : 'Cân bằng (+0%)';
        const tooltipData = `data-nature-title="${escapeHtml(nat.name)} (${escapeHtml(nat.en)})" data-nature-buff="${escapeHtml(buffDesc)}" data-nature-desc="${escapeHtml(nat.desc)}"`;
        natureBadgeHtml = `<span class="nature-pill ${pillTypeClass}" ${tooltipData} title="${escapeHtml(nat.name)}: ${escapeHtml(buffDesc)}">${escapeHtml(nat.name)}</span>`;
        chipTooltip = tooltipData;
      } else {
        chipTooltip = `data-nature-title="${escapeHtml(pet.name)}" data-nature-buff="Chưa có dữ liệu tính cách" data-nature-desc="Bấm Đồng bộ để cập nhật kho Pet từ máy chủ game."`;
      }

      return `<span class="${cls}" ${chipTooltip}>${icon}${escapeHtml(pet.name)}${natureBadgeHtml}</span>`;
    }).join('');

    tr.innerHTML = `
      <td>${startIdx + idx + 1}</td>
      <td>
        <span class="copyable-cell copy-user" data-copy="${escapeHtml(acc.username)}" title="Bấm để copy">
          <strong>${escapeHtml(acc.username)}</strong> 📑
        </span>
      </td>
      <td>
        <span class="copyable-cell copy-pwd pwd-text" data-copy="${escapeHtml(acc.password)}" title="Bấm để copy mật khẩu">
          ${escapeHtml(acc.password)} 📑
        </span>
      </td>
      <td>${escapeHtml(acc.character_name || '')}</td>
      <td><span class="badge-normal" style="padding: 3px 7px;">S${escapeHtml(acc.zone_id || '')}</span></td>
      <td>${resultBadge}</td>
      <td>
        <div class="pet-chips-container">
          ${isPending
            ? '<span style="color: #f59e0b; font-size: 12px; font-style: italic;">⏳ Chờ kết nối máy chủ để nhận 20 vé &amp; rút pet...</span>'
            : (petChipsHtml || '<span style="color: var(--text-dim);">Chưa rút</span>')
          }
        </div>
        ${acc.lucky_sigh ? `
        <div class="lucky-sigh-container" style="margin-top: 5px;">
          <span class="lucky-sigh-chip" style="${resolvedHit.itemIsHit ? 'background: rgba(244, 63, 94, 0.35); color: #fff; border: 1.5px solid #f43f5e; box-shadow: 0 0 10px rgba(244, 63, 94, 0.5);' : 'background: rgba(244, 63, 94, 0.15); color: #fda4af; border: 1px solid rgba(244, 63, 94, 0.4);'} border-radius: 5px; padding: 2px 8px; font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;" title="Phần thưởng nhận từ Quẻ May Mắn">
            ${resolvedHit.itemIsHit ? '🎯 ' : ''}🎋 Quẻ: <b style="color: #fff;">${escapeHtml(acc.lucky_sigh)}</b>
          </span>
        </div>
        ` : ''}
      </td>
      <td>
        <div class="action-btn-group">
          ${isPending ? `
          <button type="button" class="btn-resume-row resume-single-btn" data-user="${escapeHtml(acc.username)}" title="Chạy tiếp nhận 20 vé và rút pet">
            ▶️ Tiếp tục
          </button>` : ''}
          <button type="button" class="btn-sync-row sync-single-btn" data-user="${escapeHtml(acc.username)}" title="Đồng bộ lại kho Pet từ Game Server">
            🔄 Đồng bộ
          </button>
          <button type="button" class="btn-secondary btn-copy-row copy-full-btn" data-user="${escapeHtml(acc.username)}" data-raw="${escapeHtml(acc.raw || '')}" title="Copy username|password|pet trúng">
            📋 Copy
          </button>
          <button type="button" class="delete-acc-btn" data-user="${escapeHtml(acc.username)}" title="Xóa tài khoản này" aria-label="Xóa tài khoản">
            🗑️
          </button>
        </div>
      </td>
    `;

    fragment.appendChild(tr);
  });

  accountsTbody.appendChild(fragment);
  if (resetScroll && accountsTableScroll) {
    accountsTableScroll.scrollTop = 0;
  }
}

// Single Event Delegation for Accounts Table
if (accountsTbody) {
  accountsTbody.addEventListener('click', async (e) => {
    const copyUser = e.target.closest('.copy-user');
    if (copyUser) {
      await window.electronAPI.copyToClipboard(copyUser.dataset.copy);
      showToast(`Đã copy username: ${copyUser.dataset.copy}`);
      return;
    }

    const copyPwd = e.target.closest('.copy-pwd');
    if (copyPwd) {
      await window.electronAPI.copyToClipboard(copyPwd.dataset.copy);
      showToast('Đã copy mật khẩu!');
      return;
    }

    const copyFull = e.target.closest('.copy-full-btn');
    if (copyFull) {
      const user = copyFull.dataset.user;
      const acc = accountsList.find(a => a.username === user);
      if (acc) {
        const { hitObjects } = checkAccountTargetHit(acc);
        const parsedPets = (acc.pets || []).map(parsePetEntry);
        let petStr = '';
        if (hitObjects && hitObjects.length > 0) {
          petStr = hitObjects.map(p => p.nature?.name ? `${p.name} (${p.nature.name})` : p.name).join(', ');
        } else if (parsedPets.length > 0) {
          petStr = parsedPets.map(p => p.nature?.name ? `${p.name} (${p.nature.name})` : p.name).join(', ');
        } else {
          petStr = 'Chưa rút';
        }
        const luckyStr = acc.lucky_sigh ? `|Quẻ: ${acc.lucky_sigh}` : '';
        const copyText = `${acc.username}|${acc.password}|${petStr}${luckyStr}`;
        await window.electronAPI.copyToClipboard(copyText);
        showToast(`Đã copy: ${copyText}`, '📋');
      } else {
        await window.electronAPI.copyToClipboard(copyFull.dataset.raw || '');
        showToast('Đã copy thông tin tài khoản!');
      }
      return;
    }

    const syncBtn = e.target.closest('.sync-single-btn');
    if (syncBtn) {
      const user = syncBtn.dataset.user;
      if (!user || syncBtn.disabled) return;
      const originalHtml = syncBtn.innerHTML;
      syncBtn.disabled = true;
      syncBtn.innerHTML = '⏳ Đang đọc...';
      showToast(`Đang kết nối Socket để đồng bộ kho Pet cho ${user}...`, '🔄');
      try {
        const res = await window.electronAPI.syncAccountPets(user);
        if (res && res.success) {
          const acc = accountsList.find(a => a.username === user);
          if (acc) {
            acc.pets = res.pets || [];
            acc.status = 'completed';
          }
          updateMetrics();
          renderAccountsTable();
          showToast(`🎉 Đồng bộ thành công ${user}: ${res.count} Pet trong kho server!`, '✅');
        } else {
          showToast(`❌ Lỗi đồng bộ ${user}: ${(res && res.message) || 'Không có phản hồi'}`, '⚠️');
          syncBtn.disabled = false;
          syncBtn.innerHTML = originalHtml;
        }
      } catch (err) {
        const errMsg = typeof err === 'string' ? err : ((err && err.message) || JSON.stringify(err));
        showToast(`❌ Lỗi: ${errMsg}`, '⚠️');
        syncBtn.disabled = false;
        syncBtn.innerHTML = originalHtml;
      }
      return;
    }

    const resumeBtn = e.target.closest('.resume-single-btn');
    if (resumeBtn) {
      const user = resumeBtn.dataset.user;
      if (!user) return;
      if (isRunning) {
        showToast('Đang có tiến trình chạy! Vui lòng dừng lại trước.', '⚠️');
        return;
      }
      setRunningState(true, 'resume');
      resumeBtn.disabled = true;
      resumeBtn.textContent = '⏳ Đang chạy...';
      const tabConsoleBtn = document.querySelector('.tab-btn[data-tab="tab-console"]');
      if (tabConsoleBtn) tabConsoleBtn.click();
      addLogLine(`⚡ Bắt đầu chạy tiếp tài khoản: ${user}...`, 'normal');
      const isProxyMode = radioNetProxy ? radioNetProxy.checked : false;
      const networkMode = isProxyMode ? 'proxy' : 'direct';
      const rawProxies = getValidProxyList();
      const proxyType = selectProxyType ? selectProxyType.value : 'socks5';
      const res = await window.electronAPI.resumePending({
        username: user,
        threads: 1,
        proxies: rawProxies,
        networkMode,
        proxyType
      });
      if (!res || !res.success) {
        addLogLine(`❌ Không thể chạy tiếp: ${(res && res.message) || 'Lỗi không xác định'}`, 'warning');
        showToast((res && res.message) || 'Không thể chạy tiếp', '⚠️');
        resumeBtn.disabled = false;
        resumeBtn.textContent = '▶️ Tiếp tục';
        setRunningState(false);
      } else {
        showToast(`Đang chạy tiếp tài khoản ${user}`, '⚡');
      }
      return;
    }

    const delBtn = e.target.closest('.delete-acc-btn');
    if (delBtn) {
      const user = delBtn.dataset.user;
      const ok = await window.electronAPI.deleteAccount(user);
      if (ok) {
        showToast(`Đã xóa tài khoản: ${user}`, '🗑️');
        await reloadAccounts(true);
      } else {
        showToast(`Không thể xóa tài khoản ${user}`, '❌');
      }
    }
  });
}

// Global resume pending accounts
if (btnResumePending) {
  btnResumePending.addEventListener('click', async () => {
    if (isRunning) {
      addLogLine('⏹️ Đang gửi tín hiệu dừng tiến trình...', 'warning');
      await window.electronAPI.stopTask();
      setRunningState(false);
      showToast('Đã gửi yêu cầu dừng tiến trình!', '⏹️');
      return;
    }

    const pendingList = accountsList.filter(a => a.status === 'pending_reward' || a.status === 'pending_draw');
    if (pendingList.length === 0) {
      showToast('Không có tài khoản nào đang chờ!', 'ℹ️');
      return;
    }
    const tabConsoleBtn = document.querySelector('.tab-btn[data-tab="tab-console"]');
    if (tabConsoleBtn) tabConsoleBtn.click();
    const threads = Math.max(1, parseInt((inputThreads && inputThreads.value) || (inputThreadsRange && inputThreadsRange.value) || 1, 10));
    const isProxyMode = radioNetProxy ? radioNetProxy.checked : false;
    const networkMode = isProxyMode ? 'proxy' : 'direct';
    const rawProxies = getValidProxyList();
    const proxyType = selectProxyType ? selectProxyType.value : 'socks5';

    setRunningState(true, 'resume');
    addLogLine(`⚡ Bắt đầu chạy tiếp ${pendingList.length} tài khoản đang chờ nhận vé / rút pet (${threads} luồng, ${networkMode === 'proxy' ? `${rawProxies.length} proxy` : 'mạng gốc'})...`, 'normal');
    const res = await window.electronAPI.resumePending({
      username: null,
      threads,
      proxies: rawProxies,
      networkMode,
      proxyType
    });
    if (!res || !res.success) {
      addLogLine(`❌ Không thể chạy tiếp: ${(res && res.message) || 'Lỗi không xác định'}`, 'warning');
      showToast((res && res.message) || 'Không thể chạy tiếp', '⚠️');
      setRunningState(false);
    } else {
      showToast(`Đang chạy tiếp ${pendingList.length} tài khoản chờ...`, '⚡');
    }
  });
}

// ==========================================
// SMART DELETION CONTROLLER
// ==========================================
function getSmartDeleteCategoryInfo() {
  let categoryName = 'Trúng Pet';
  let labelTemplate = (c) => `🗑️ Xóa All Trúng Pet (${c})`;

  if (currentAccFilter === 'miss') {
    categoryName = 'Acc Trượt';
    labelTemplate = (c) => `🗑️ Xóa All Acc Trượt (${c})`;
  } else if (currentAccFilter === 'pending') {
    categoryName = 'Chờ Nhận Vé';
    labelTemplate = (c) => `🗑️ Xóa All Chờ Nhận Vé (${c})`;
  } else if (currentAccFilter === 'all') {
    categoryName = 'Tất Cả';
    labelTemplate = (c) => `🗑️ Xóa All Tài Khoản (${c})`;
  }

  return { categoryName, labelTemplate };
}

function updateSmartDeleteButton() {
  if (!btnDeleteFailed) return;
  const count = Array.isArray(currentFilteredAccounts) ? currentFilteredAccounts.length : 0;
  const { categoryName, labelTemplate } = getSmartDeleteCategoryInfo();
  btnDeleteFailed.textContent = labelTemplate(count);
  btnDeleteFailed.title = `Xóa toàn bộ ${count} tài khoản ${categoryName} đang hiển thị`;
}

if (btnDeleteFailed) {
  btnDeleteFailed.addEventListener('click', async () => {
    const targets = Array.isArray(currentFilteredAccounts) ? currentFilteredAccounts : [];
    const count = targets.length;
    const { categoryName } = getSmartDeleteCategoryInfo();

    if (count === 0) {
      showToast('Không có tài khoản nào phù hợp để xóa!', 'ℹ️');
      return;
    }

    const confirmed = window.confirm(
      `Bạn có chắc chắn muốn XÓA VĨNH VIỄN ${count} tài khoản ${categoryName} khỏi bảng và CSDL không?`
    );
    if (!confirmed) return;

    const usernamesToDelete = targets.map((a) => a.username);
    const toDeleteSet = new Set(usernamesToDelete);

    accountsList = accountsList.filter((a) => !toDeleteSet.has(a.username));
    currentAccPage = 1;
    updateMetrics();
    renderAccountsTable({ resetScroll: true });

    try {
      const ok = await window.electronAPI.deleteAccounts(usernamesToDelete);
      if (ok) {
        showToast(`Đã xóa thành công ${count} tài khoản ${categoryName}!`, '🗑️');
      } else {
        showToast(`Có lỗi xảy ra khi xóa ${count} tài khoản khỏi CSDL`, '⚠️');
        await reloadAccounts(true);
      }
    } catch (err) {
      console.error('Lỗi deleteAccounts:', err);
      showToast('Có lỗi xảy ra khi xóa tài khoản khỏi CSDL', '⚠️');
      await reloadAccounts(true);
    }
  });
}

if (inputSearchAcc) {
  inputSearchAcc.addEventListener('input', () => {
    if (searchAccDebounceTimer) clearTimeout(searchAccDebounceTimer);
    searchAccDebounceTimer = setTimeout(() => {
      searchAccDebounceTimer = null;
      currentAccPage = 1;
      renderAccountsTable({ resetScroll: true });
    }, 150);
  });
}

// Pagination Controls Event Listeners
if (selectAccPageSize) {
  selectAccPageSize.addEventListener('change', () => {
    const val = parseInt(selectAccPageSize.value, 10);
    if (ALLOWED_ACC_PAGE_SIZES.includes(val)) {
      accPageSize = val;
      safeStorageSet(STORAGE_KEY_ACC_PAGE_SIZE, String(val));
      currentAccPage = 1;
      renderAccountsTable({ resetScroll: true });
    }
  });
}

if (btnAccPageFirst) {
  btnAccPageFirst.addEventListener('click', () => {
    if (currentAccPage > 1) {
      currentAccPage = 1;
      renderAccountsTable({ resetScroll: true });
    }
  });
}

if (btnAccPagePrev) {
  btnAccPagePrev.addEventListener('click', () => {
    if (currentAccPage > 1) {
      currentAccPage--;
      renderAccountsTable({ resetScroll: true });
    }
  });
}

if (btnAccPageNext) {
  btnAccPageNext.addEventListener('click', () => {
    const totalPages = Math.max(1, Math.ceil(currentFilteredAccounts.length / accPageSize));
    if (currentAccPage < totalPages) {
      currentAccPage++;
      renderAccountsTable({ resetScroll: true });
    }
  });
}

if (btnAccPageLast) {
  btnAccPageLast.addEventListener('click', () => {
    const totalPages = Math.max(1, Math.ceil(currentFilteredAccounts.length / accPageSize));
    if (currentAccPage < totalPages) {
      currentAccPage = totalPages;
      renderAccountsTable({ resetScroll: true });
    }
  });
}

if (accPaginationPages) {
  accPaginationPages.addEventListener('click', (e) => {
    const pageBtn = e.target.closest('.page-num-btn');
    if (!pageBtn) return;
    const targetPage = parseInt(pageBtn.dataset.page, 10);
    if (targetPage && targetPage !== currentAccPage) {
      currentAccPage = targetPage;
      renderAccountsTable({ resetScroll: true });
    }
  });
}

// ================= Viewport-Bounded Export Dropdown (3 Formats) =================
const dropdownExportWrapper = document.getElementById('dropdown-export-wrapper');
const dropdownExportMenu = document.getElementById('dropdown-export-menu');
const dropdownExportItems = document.querySelectorAll('.dropdown-export-item');

function getAccountsForExport() {
  if (currentAccFilter === 'all') {
    return accountsList;
  }
  if (currentAccFilter === 'miss') {
    return accountsList.filter(acc => {
      const isPending = acc.status === 'pending_reward' || acc.status === 'pending_draw' || (acc.status && acc.status.includes('chờ'));
      return !isPending && !checkAccountTargetHit(acc).isHit;
    });
  }
  if (currentAccFilter === 'pending') {
    return accountsList.filter(acc =>
      acc.status === 'pending_reward' || acc.status === 'pending_draw' || (acc.status && acc.status.includes('chờ'))
    );
  }
  const hitAccs = accountsList.filter(acc => {
    const isPending = acc.status === 'pending_reward' || acc.status === 'pending_draw';
    return !isPending && checkAccountTargetHit(acc).isHit;
  });
  return hitAccs.length > 0 ? hitAccs : accountsList;
}

function formatAccountsList(exportList, format = 'standard') {
  if (format === 'two_lines') {
    return exportList.map(acc => `tk: ${acc.username}\nmk: ${acc.password}`).join('\n\n');
  }
  if (format === 'user_pass') {
    return exportList.map(acc => `${acc.username}|${acc.password}`).join('\n');
  }
  return exportList.map(acc => {
    const { hitPets } = checkAccountTargetHit(acc);
    const pokeStr = hitPets.length > 0 ? hitPets.join(',') : (acc.pets ? acc.pets.join(',') : '');
    const luckyStr = acc.lucky_sigh ? `|Quẻ: ${acc.lucky_sigh}` : '';
    return `${acc.username}|${acc.password}|${pokeStr}${luckyStr}`;
  }).join('\n');
}

function positionExportDropdownMenu() {
  if (!dropdownExportWrapper || !dropdownExportMenu || !btnExportTxt) return;
  if (!dropdownExportWrapper.classList.contains('open')) return;

  const btnRect = btnExportTxt.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const margin = 12;

  dropdownExportMenu.style.position = 'fixed';
  dropdownExportMenu.style.right = 'auto';
  dropdownExportMenu.style.bottom = 'auto';

  const menuRect = dropdownExportMenu.getBoundingClientRect();
  const menuWidth = Math.min(menuRect.width || 300, vw - margin * 2);
  const menuHeight = menuRect.height || 190;

  let left = btnRect.right - menuWidth;
  if (left < margin) left = margin;
  if (left + menuWidth > vw - margin) left = vw - menuWidth - margin;

  let top = btnRect.bottom + 6;
  if (top + menuHeight > vh - margin && btnRect.top - menuHeight - 6 >= margin) {
    top = btnRect.top - menuHeight - 6;
  } else if (top + menuHeight > vh - margin) {
    top = Math.max(margin, vh - menuHeight - margin);
  }

  dropdownExportMenu.style.left = `${Math.round(left)}px`;
  dropdownExportMenu.style.top = `${Math.round(top)}px`;
}

function closeExportDropdown() {
  if (!dropdownExportWrapper) return;
  dropdownExportWrapper.classList.remove('open');
  if (btnExportTxt) btnExportTxt.setAttribute('aria-expanded', 'false');
}

if (btnExportTxt && dropdownExportWrapper) {
  btnExportTxt.addEventListener('click', (e) => {
    e.stopPropagation();
    const willOpen = !dropdownExportWrapper.classList.contains('open');
    if (willOpen) {
      dropdownExportWrapper.classList.add('open');
      btnExportTxt.setAttribute('aria-expanded', 'true');
      requestAnimationFrame(positionExportDropdownMenu);
    } else {
      closeExportDropdown();
    }
  });

  document.addEventListener('click', (e) => {
    if (!dropdownExportWrapper.contains(e.target)) {
      closeExportDropdown();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeExportDropdown();
    }
  });

  window.addEventListener('resize', () => {
    if (dropdownExportWrapper.classList.contains('open')) {
      positionExportDropdownMenu();
    }
  });

  window.addEventListener('scroll', () => {
    if (dropdownExportWrapper.classList.contains('open')) {
      positionExportDropdownMenu();
    }
  }, true);

  dropdownExportItems.forEach(item => {
    item.addEventListener('click', async (e) => {
      e.stopPropagation();
      closeExportDropdown();
      const format = item.dataset.format || 'standard';
      const exportList = getAccountsForExport();

      if (exportList.length === 0) {
        showToast('Chưa có tài khoản nào phù hợp để copy!', '⚠️');
        return;
      }

      const formatLabel = format === 'two_lines'
        ? '2 dòng (Cách dòng mỗi TK)'
        : (format === 'user_pass' ? 'chuẩn (tk|mk)' : 'kèm Pet (Gốc)');
      const fileContent = formatAccountsList(exportList, format);

      const ok = await window.electronAPI.copyToClipboard(fileContent);
      if (ok) {
        showToast(`Đã copy ${exportList.length} tài khoản [${formatLabel}] vào bộ nhớ tạm!`, '📋');
      } else {
        showToast('Trình duyệt chặn copy tự động. Hãy dùng nút "💾 Tải .txt"!', '⚠️');
      }
    });
  });
}

if (btnDownloadTxt) {
  btnDownloadTxt.addEventListener('click', async () => {
    const exportList = getAccountsForExport();
    if (exportList.length === 0) {
      showToast('Chưa có tài khoản nào phù hợp để tải file!', '⚠️');
      return;
    }
    const content = formatAccountsList(exportList, 'standard');
    const res = await window.electronAPI.exportTargetAccounts({
      content,
      filename: `pokemon_accounts_${currentAccFilter}`
    });
    if (res && res.success) {
      showToast(`Đã tải xuống ${exportList.length} tài khoản (${res.fileName || '.txt'})!`, '💾');
    } else {
      showToast((res && res.error) || 'Không thể tải xuống file .txt', '❌');
    }
  });
}

if (btnOpenFolder) {
  btnOpenFolder.addEventListener('click', async () => {
    await window.electronAPI.openExportFolder();
  });
}

// ================= Metrics & Pet Collection =================
function updateMetrics() {
  if (metricAccounts) metricAccounts.textContent = accountsList.length;
  if (accTabBadge) accTabBadge.textContent = accountsList.length;

  let totalDraws = 0;
  let totalPets = 0;
  let totalLegendaries = 0;

  accountsList.forEach(acc => {
    if (acc.pets && acc.pets.length > 0) {
      totalDraws += 21;
      totalPets += acc.pets.length;

      acc.pets.forEach(p => {
        if (LEGENDARY_PETS.has(parsePetEntry(p).name)) {
          totalLegendaries++;
        }
      });
    }
  });

  if (metricDraws) metricDraws.textContent = totalDraws;
  if (metricPets) metricPets.textContent = totalPets;
  if (metricLegendaries) metricLegendaries.textContent = totalLegendaries;
}

function renderPetCollection() {
  if (!petsCollection) return;
  petsCollection.innerHTML = '';
  const petFrequency = {};

  accountsList.forEach(acc => {
    if (acc.pets && acc.pets.length > 0) {
      acc.pets.forEach(p => {
        const pName = parsePetEntry(p).name;
        if (pName) petFrequency[pName] = (petFrequency[pName] || 0) + 1;
      });
    }
  });

  const sortedPets = Object.keys(petFrequency).sort((a, b) => {
    const aLeg = LEGENDARY_PETS.has(a) ? 1 : 0;
    const bLeg = LEGENDARY_PETS.has(b) ? 1 : 0;
    if (aLeg !== bLeg) return bLeg - aLeg;
    return petFrequency[b] - petFrequency[a];
  });

  if (sortedPets.length === 0) {
    petsCollection.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-dim); padding: 40px;">Chưa có Pokémon nào được ấp thành công.</div>`;
    return;
  }

  const fragment = document.createDocumentFragment();

  sortedPets.forEach(petName => {
    const count = petFrequency[petName];
    const isLegendary = LEGENDARY_PETS.has(petName);
    const isRare = RARE_PETS.has(petName);

    let tierCls = 'tier-common';
    let tierText = 'Thường';
    let avatarIcon = '🐾';

    if (isLegendary) {
      tierCls = 'tier-legendary';
      tierText = 'Thần Thú (Legendary)';
      avatarIcon = '🌟';
    } else if (isRare) {
      tierCls = 'tier-rare';
      tierText = 'Hiếm (Rare)';
      avatarIcon = '✨';
    }

    const card = document.createElement('div');
    card.className = `pet-card ${tierCls}`;
    card.innerHTML = `
      <span class="pet-count-badge">x${count}</span>
      <div class="pet-avatar">${avatarIcon}</div>
      <div class="pet-name">${escapeHtml(petName)}</div>
      <div class="pet-tier">${tierText}</div>
    `;
    fragment.appendChild(card);
  });

  petsCollection.appendChild(fragment);
}

// ================= Error Log Management =================
let errorsHistory = [];
let currentProcessingUsername = 'N/A';
let currentProcessingStage = 'Khởi tạo';
const threadUserMap = new Map();
const threadStageMap = new Map();
const threadLogsMap = new Map();
const accountLogsMap = new Map();
let activeModalErrorItem = null;

const btnTabErrors = document.getElementById('btn-tab-errors');
const errorTabBadge = document.getElementById('error-tab-badge');
const errorsTbody = document.getElementById('errors-tbody');
const btnCopyErrors = document.getElementById('btn-copy-errors');
const btnClearErrors = document.getElementById('btn-clear-errors');

const modalErrorFlow = document.getElementById('modal-error-flow');
const modalFlowAccount = document.getElementById('modal-flow-account');
const modalFlowSubtitle = document.getElementById('modal-flow-subtitle');
const modalFlowDetail = document.getElementById('modal-flow-detail');
const modalFlowSuggestion = document.getElementById('modal-flow-suggestion');
const modalFlowStepCount = document.getElementById('modal-flow-step-count');
const modalFlowTimeline = document.getElementById('modal-flow-timeline');
const btnCloseFlowModal = document.getElementById('btn-close-flow-modal');
const btnCloseFlowModalFooter = document.getElementById('btn-close-flow-modal-footer');
const btnCopyModalFlow = document.getElementById('btn-copy-modal-flow');

function updateErrorBadge() {
  if (errorTabBadge) {
    errorTabBadge.textContent = errorsHistory.length;
  }
  if (btnTabErrors) {
    btnTabErrors.classList.toggle('has-errors', errorsHistory.length > 0);
  }
}

function renderErrorsTable() {
  if (!errorsTbody) return;
  errorsTbody.innerHTML = '';

  if (errorsHistory.length === 0) {
    errorsTbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: var(--text-dim); padding: 36px;">
          🎉 Chưa có lỗi nào phát sinh trong phiên chạy này! Hệ thống đang hoạt động hoàn hảo.
        </td>
      </tr>
    `;
    return;
  }

  const fragment = document.createDocumentFragment();
  [...errorsHistory].reverse().forEach((err, idx) => {
    const tr = document.createElement('tr');
    tr.className = 'error-row-clickable';
    tr.dataset.errId = String(err.id);
    tr.title = 'Bấm vào dòng này để mở cửa sổ xem toàn bộ flow lỗi';
    const stepCount = (err.flow || []).length;
    tr.innerHTML = `
      <td>${errorsHistory.length - idx}</td>
      <td style="color: var(--text-muted); font-family: monospace;">${escapeHtml(err.time)}</td>
      <td>
        <strong style="color: #38bdf8;">${escapeHtml(err.account)}</strong>
        <span class="badge-tag-opt" style="font-size: 10px; margin-left: 6px; padding: 1px 6px;">${stepCount} bước</span>
      </td>
      <td><span class="error-badge-stage">${escapeHtml(err.stage)}</span></td>
      <td><span class="error-badge-reason" title="${escapeHtml(err.detail)}">${escapeHtml(err.detail)}</span></td>
      <td><span class="error-badge-tip">${escapeHtml(err.suggestion)}</span></td>
      <td style="text-align: center; white-space: nowrap;">
        <div class="action-btn-group" style="justify-content: center;">
          <button type="button" class="btn-view-flow view-flow-btn" data-err-id="${err.id}" title="Xem chi tiết toàn bộ quy trình flow">
            🔍 Xem Flow
          </button>
          <button type="button" class="btn-secondary btn-copy-row copy-single-error-btn" data-err="${escapeHtml(err.time + ' | ' + err.account + ' | ' + err.stage + ' | ' + err.detail)}" title="Copy tóm tắt lỗi">
            📋
          </button>
        </div>
      </td>
    `;
    fragment.appendChild(tr);
  });
  errorsTbody.appendChild(fragment);
}

function openErrorFlowModal(err) {
  if (!err || !modalErrorFlow) return;
  activeModalErrorItem = err;
  if (modalFlowAccount) modalFlowAccount.textContent = err.account;
  if (modalFlowSubtitle) modalFlowSubtitle.textContent = `Giai đoạn: ${err.stage} • Thời gian: ${err.time} • Lỗi #${err.id}`;
  if (modalFlowDetail) modalFlowDetail.textContent = err.detail;
  if (modalFlowSuggestion) modalFlowSuggestion.textContent = err.suggestion;

  const flow = err.flow || [];
  if (modalFlowStepCount) modalFlowStepCount.textContent = flow.length;

  if (modalFlowTimeline) {
    modalFlowTimeline.innerHTML = '';
    if (flow.length === 0) {
      modalFlowTimeline.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); padding: 24px;">
          Lỗi xảy ra ngay khi vừa bắt đầu tiến trình hoặc chưa có log chi tiết trước đó.
        </div>
      `;
    } else {
      const frag = document.createDocumentFragment();
      flow.forEach((step, sIdx) => {
        const isLast = (sIdx === flow.length - 1);
        const div = document.createElement('div');
        div.className = `flow-timeline-item ${isLast ? 'is-error-step' : ''}`;

        let badgeType = 'info';
        let badgeLabel = 'INFO';
        const lowerTxt = (step.text || '').toLowerCase();
        if (step.type === 'error' || lowerTxt.includes('❌') || lowerTxt.includes('error') || lowerTxt.includes('thất bại') || lowerTxt.includes('alert')) {
          badgeType = 'error';
          badgeLabel = 'ERROR';
        } else if (step.type === 'warning' || lowerTxt.includes('⚠️') || lowerTxt.includes('warning')) {
          badgeType = 'warning';
          badgeLabel = 'WARN';
        } else if (step.type === 'success' || lowerTxt.includes('🎉') || lowerTxt.includes('thành công') || lowerTxt.includes('hoàn tất')) {
          badgeType = 'success';
          badgeLabel = 'DONE';
        }

        div.innerHTML = `
          <span class="flow-item-time">${escapeHtml(step.time || '')}</span>
          <span class="flow-item-badge flow-badge-${badgeType}">${badgeLabel}</span>
          <span class="flow-item-text">${escapeHtml(step.text || '')}</span>
        `;
        frag.appendChild(div);
      });
      modalFlowTimeline.appendChild(frag);
      modalFlowTimeline.scrollTop = modalFlowTimeline.scrollHeight;
    }
  }

  modalErrorFlow.style.display = 'flex';
}

function closeErrorFlowModal() {
  if (modalErrorFlow) {
    modalErrorFlow.style.display = 'none';
  }
  activeModalErrorItem = null;
}

if (btnCloseFlowModal) btnCloseFlowModal.addEventListener('click', closeErrorFlowModal);
if (btnCloseFlowModalFooter) btnCloseFlowModalFooter.addEventListener('click', closeErrorFlowModal);
if (modalErrorFlow) {
  modalErrorFlow.addEventListener('click', (e) => {
    if (e.target === modalErrorFlow) closeErrorFlowModal();
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && modalErrorFlow && modalErrorFlow.style.display === 'flex') {
    closeErrorFlowModal();
  }
});

if (btnCopyModalFlow) {
  btnCopyModalFlow.addEventListener('click', async () => {
    if (!activeModalErrorItem) return;
    const err = activeModalErrorItem;
    const flow = err.flow || [];
    const flowLines = flow.map(s => `[${s.time}] [${String(s.type || 'info').toUpperCase()}] ${s.text}`);
    const fullText = [
      '====================================================',
      'CHI TIẾT QUY TRÌNH LỖI (ACCOUNT EXECUTION FLOW)',
      `Tài khoản: ${err.account}`,
      `Giai đoạn lỗi: ${err.stage}`,
      `Thời gian: ${err.time}`,
      `Chi tiết lỗi: ${err.detail}`,
      `Gợi ý xử lý: ${err.suggestion}`,
      '----------------------------------------------------',
      'TOÀN BỘ CÁC BƯỚC THỰC THI (FLOW):',
      flowLines.length > 0 ? flowLines.join('\n') : '(Không có thêm log flow)',
      '===================================================='
    ].join('\n');

    await window.electronAPI.copyToClipboard(fullText);
    showToast(`Đã copy toàn bộ flow của ${err.account}!`, '📋');
  });
}

if (btnCopyErrors) {
  btnCopyErrors.addEventListener('click', async () => {
    if (errorsHistory.length === 0) {
      showToast('Chưa có lỗi nào để copy!', 'ℹ️');
      return;
    }
    const lines = errorsHistory.map(e => `[${e.time}] [TK: ${e.account}] [${e.stage}] ${e.detail} -> ${e.suggestion}`);
    await window.electronAPI.copyToClipboard(lines.join('\n'));
    showToast(`Đã copy ${errorsHistory.length} mục lỗi vào clipboard!`, '📋');
  });
}

if (btnClearErrors) {
  btnClearErrors.addEventListener('click', () => {
    if (errorsHistory.length === 0) return;
    errorsHistory = [];
    threadLogsMap.clear();
    accountLogsMap.clear();
    updateErrorBadge();
    renderErrorsTable();
    showToast('Đã xóa sạch nhật ký lỗi!', '🗑️');
  });
}

if (errorsTbody) {
  errorsTbody.addEventListener('click', async (e) => {
    const copyBtn = e.target.closest('.copy-single-error-btn');
    if (copyBtn) {
      e.stopPropagation();
      await window.electronAPI.copyToClipboard(copyBtn.dataset.err);
      showToast('Đã copy tóm tắt lỗi!');
      return;
    }

    const row = e.target.closest('.error-row-clickable');
    if (row) {
      const errId = parseInt(row.dataset.errId, 10);
      const err = errorsHistory.find(item => item.id === errId);
      if (err) {
        openErrorFlowModal(err);
      }
    }
  });
}

// ================= Realtime WebSocket / Bridge Listeners =================
window.electronAPI.onLog((payload) => {
  if (!payload) return;
  addLogLine(payload.text, payload.type, payload.time);

  const txt = payload.text || '';
  const threadMatch = txt.match(/\[Luồng\s*#(\d+)/i);
  const threadKey = threadMatch ? threadMatch[1] : '1';

  if (txt.includes('[Tài khoản ')) {
    threadLogsMap.set(threadKey, []);
    threadUserMap.delete(threadKey);
    threadStageMap.set(threadKey, 'Khởi tạo');
  }

  let matchedStage = null;
  if (txt.includes('Step 1:') || txt.includes('initSDK')) {
    matchedStage = 'Bước 1: Init SDK';
  } else if (txt.includes('Step 2:') || txt.includes('Registering') || txt.includes('Target Username:')) {
    matchedStage = 'Bước 2: Tạo tài khoản';
  } else if (txt.includes('Step 3:') || txt.includes('Binding user') || txt.includes('Gán Server')) {
    matchedStage = 'Bước 3: Gán Server Zone';
  } else if (txt.includes('Step 4:') || txt.includes('Creating character') || txt.includes('Tạo nhân vật')) {
    matchedStage = 'Bước 4: Tạo nhân vật (Socket)';
  } else if (txt.includes('Step 5:') || txt.includes('Web Activity') || txt.includes('Triggering Web') || txt.includes('vé web')) {
    matchedStage = 'Bước 5: Nhận 20 vé Web';
  } else if (txt.includes('Step 6:') || txt.includes('claim mailbox') || txt.includes('Ấp Cao Cấp') || txt.includes('rút pet') || txt.includes('Lượt Rút') || txt.includes('Free draw')) {
    matchedStage = 'Bước 6: Nhận thư & Ấp 21 lượt';
  }

  if (matchedStage) {
    currentProcessingStage = matchedStage;
    threadStageMap.set(threadKey, matchedStage);
  }

  const matchUser = txt.match(/Chạy tiếp tài khoản:\s*([a-zA-Z0-9_]+)/i) ||
                    txt.match(/Target Username:\s*([a-zA-Z0-9_]+)/i) ||
                    txt.match(/Registering direct account:\s*([a-zA-Z0-9_]+)/i) ||
                    txt.match(/Upgrading visitor \d+ to\s*['"]?([a-zA-Z0-9_]+)['"]?/i) ||
                    txt.match(/Account ready:\s*([a-zA-Z0-9_]+)/i) ||
                    txt.match(/Claiming .*? for\s+([a-zA-Z0-9_]{3,})/i) ||
                    txt.match(/cho\s+(?:tài khoản\s*)?['"]?([a-zA-Z0-9_]{3,})['"]?/i) ||
                    txt.match(/tài khoản\s*['":]+\s*([a-zA-Z0-9_]+)/i);

  if (matchUser && matchUser[1]) {
    const rawU = matchUser[1].trim();
    const ignoreList = new Set([
      'này', 'mới', 'du', 'khách', 'đang', 'chờ', 'thành', 'công', 'lỗi',
      'socket', 'được', 'web', 'game', 'null', 'undefined', 'user', 'uid',
      'zone', 'server', 'visitor', 'sdk', 'account'
    ]);
    if (!ignoreList.has(rawU.toLowerCase()) && rawU.length >= 3 && !/^\d+$/.test(rawU)) {
      currentProcessingUsername = rawU;
      threadUserMap.set(threadKey, rawU);
    }
  }

  const currentStageName = matchedStage || threadStageMap.get(threadKey) || currentProcessingStage || 'Khởi tạo';
  const stepItem = {
    time: payload.time || new Date().toLocaleTimeString(),
    text: txt,
    type: payload.type || 'info',
    stage: currentStageName
  };

  if (!threadLogsMap.has(threadKey)) threadLogsMap.set(threadKey, []);
  const tLogs = threadLogsMap.get(threadKey);
  tLogs.push(stepItem);
  if (tLogs.length > 80) tLogs.shift();

  const activeUser = threadUserMap.get(threadKey) || currentProcessingUsername;
  if (activeUser && activeUser !== 'N/A') {
    if (!accountLogsMap.has(activeUser)) {
      accountLogsMap.set(activeUser, [...tLogs]);
    } else {
      const aLogs = accountLogsMap.get(activeUser);
      if (aLogs.length === 0 || aLogs[aLogs.length - 1].text !== txt) {
        aLogs.push(stepItem);
        if (aLogs.length > 80) aLogs.shift();
      }
    }
  }

  const isError = payload.type === 'warning' ||
                  txt.includes('⚠️') ||
                  txt.includes('❌') ||
                  txt.includes('Socket error') ||
                  txt.includes('thất bại') ||
                  txt.includes('WinError');

  const isLifecycleNotice = txt.includes('Tiến trình đã kết thúc') ||
                            txt.includes('Dừng lại') ||
                            txt.includes('gửi tín hiệu') ||
                            txt.includes('FOR EDUCATIONAL PURPOSES') ||
                            txt.includes('BATCH SUMMARY') ||
                            /Failed:\s*\d+\s*❌/.test(txt) ||
                            txt.includes('Tài khoản đã tạo') ||
                            txt.includes('zone mapping') ||
                            txt.includes('proxies.txt') ||
                            /lần\s*[12]\//i.test(txt) ||
                            /attempt\s*[12]\//i.test(txt) ||
                            txt.includes('đang tự động kết nối lại') ||
                            txt.includes('đang gửi rút lại') ||
                            txt.includes('đang thử lại');

  if (isError && !isLifecycleNotice) {
    const cleanDetail = txt.replace(/^[0-9:\-\s]+(WARNING|ERROR|ALERT|INFO)\s*-\s*/, '').trim();

    let resolvedUser = threadUserMap.get(threadKey) || currentProcessingUsername;
    if ((!resolvedUser || resolvedUser === 'N/A') && threadUserMap.size > 0) {
      for (const [, u] of threadUserMap.entries()) {
        if (u && u !== 'N/A') {
          resolvedUser = u;
          break;
        }
      }
    }
    if (!resolvedUser) resolvedUser = 'N/A';

    let resolvedStage = threadStageMap.get(threadKey) || currentProcessingStage || 'Bước 6: Nhận thư & Ấp 21 lượt';
    if (cleanDetail.includes('Lượt Rút') || cleanDetail.includes('Free draw') || cleanDetail.includes('Ấp Cao Cấp') || cleanDetail.includes('Claim mailbox') || cleanDetail.includes('Nhận thư')) {
      resolvedStage = 'Bước 6: Nhận thư & Ấp 21 lượt';
    } else if (cleanDetail.includes('CreateAvatar') || cleanDetail.includes('Tạo nhân vật') || cleanDetail.includes('chưa tạo được')) {
      resolvedStage = 'Bước 4: Tạo nhân vật (Socket)';
    } else if (cleanDetail.includes('Web Activity') || cleanDetail.includes('vé web')) {
      resolvedStage = 'Bước 5: Nhận 20 vé Web';
    }

    let suggestion = 'Kiểm tra lại cấu hình hoặc thử lại đợt chạy tiếp theo.';
    if (cleanDetail.includes('108') || cleanDetail.includes('user has bind') || cleanDetail.includes('tồn tại')) {
      suggestion = 'Tên tài khoản này đã có người đăng ký / liên kết trước đó. Hãy đổi tiền tố khác hoặc bật Random.';
    } else if (cleanDetail.includes('10053') || cleanDetail.includes('10054') || cleanDetail.includes('forcibly closed') || cleanDetail.includes('aborted') || cleanDetail.includes('Socket error')) {
      suggestion = 'Máy chủ game ngắt kết nối socket do mạng lag hoặc server quá tải. Tool đã tự động kết nối lại.';
    } else if (cleanDetail.includes('timeout') || cleanDetail.includes('timed out')) {
      suggestion = 'Hết thời gian chờ phản hồi mạng. Kiểm tra đường truyền Internet.';
    } else if (cleanDetail.includes('Tạo nhân vật thất bại') || cleanDetail.includes('CreateAvatar')) {
      suggestion = 'Không thể tạo nhân vật (tên trùng hoặc máy chủ từ chối).';
    } else if (cleanDetail.includes('Visitor') || cleanDetail.includes('du khách') || cleanDetail.includes('upgrade')) {
      suggestion = 'Lỗi API luồng đăng ký du khách từ máy chủ Web.';
    }

    let flowSnapshot = [];
    if (resolvedUser && resolvedUser !== 'N/A' && accountLogsMap.has(resolvedUser)) {
      flowSnapshot = [...accountLogsMap.get(resolvedUser)];
    } else if (threadLogsMap.has(threadKey)) {
      flowSnapshot = [...threadLogsMap.get(threadKey)];
    }

    if (flowSnapshot.length === 0 || flowSnapshot[flowSnapshot.length - 1].text !== txt) {
      flowSnapshot.push({
        time: payload.time || new Date().toLocaleTimeString(),
        text: txt,
        type: 'error',
        stage: resolvedStage
      });
    }

    errorsHistory.push({
      id: errorsHistory.length + 1,
      time: payload.time || new Date().toLocaleTimeString(),
      account: resolvedUser,
      stage: resolvedStage,
      detail: cleanDetail,
      suggestion,
      flow: flowSnapshot
    });

    updateErrorBadge();
    if (currentActiveTab === 'tab-errors') {
      renderErrorsTable();
    }
  }
});

window.electronAPI.onTaskFinished((payload) => {
  setRunningState(false);
  reloadAccounts(true);
  const code = payload && payload.code !== undefined ? payload.code : 0;
  if (code === 0) {
    showToast('Đợt chạy hoàn thành thành công!', '🎉');
  } else {
    showToast(`Tiến trình dừng với mã ${code}`, '⚠️');
  }
});

if (window.electronAPI.onTaskStatus) {
  window.electronAPI.onTaskStatus((status) => {
    if (!status) return;
    setRunningState(Boolean(status.running), status.mode || 'normal');
  });
}

window.electronAPI.onAccountAdded(() => {
  if (pendingReloadTimer) return;
  pendingReloadTimer = setTimeout(() => {
    pendingReloadTimer = null;
    reloadAccounts();
  }, 600);
});

async function loadPokedexFromDb() {
  if (window.electronAPI && window.electronAPI.getPokedex) {
    const list = await window.electronAPI.getPokedex();
    if (Array.isArray(list) && list.length > 0) {
      fullPokedex = list;
      list.forEach(p => {
        if (p.tier === 'legendary') LEGENDARY_PETS.add(p.name);
        if (p.tier === 'rare') RARE_PETS.add(p.name);
      });
    }
  }
}

async function loadSavedProxiesFromDb() {
  if (!window.electronAPI || typeof window.electronAPI.getSavedProxies !== 'function') return;
  const res = await window.electronAPI.getSavedProxies();
  if (!res || !res.success || !Array.isArray(res.proxies)) return;

  if (res.proxies.length > 0 && textareaProxies) {
    textareaProxies.value = res.proxies.map(p => p.proxy).join('\n');
    safeStorageSet(STORAGE_KEY_PROXIES, textareaProxies.value);

    if (selectProxyType && res.proxyType) {
      selectProxyType.value = res.proxyType;
      safeStorageSet(STORAGE_KEY_PROXY_TYPE, res.proxyType);
    }

    proxyCheckCache.clear();
    res.proxies.forEach(p => {
      if (p.status === 'live' || p.status === 'dead') {
        const entry = {
          proxy: p.proxy,
          alive: p.status === 'live',
          live: p.status === 'live',
          latency: p.latency_ms || 0,
          error: p.error || null
        };
        proxyCheckCache.set(p.proxy, entry);
        const parts = String(p.proxy || '').split(':');
        if (parts.length >= 2) {
          proxyCheckCache.set(`${parts[0]}:${parts[1]}`, entry);
        }
      }
    });

    if (proxyCountBadge) {
      proxyCountBadge.textContent = `${res.proxies.length} proxy`;
    }
    if (proxyCheckStatus) {
      const checkedCount = (res.alive || 0) + (res.dead || 0);
      if (checkedCount > 0) {
        proxyCheckStatus.innerHTML = `<span style="color: #38bdf8; font-weight: 600;">💾 Đã tải ${res.total} proxy từ CSDL</span> <span style="color: #34d399; margin-left: 6px;">(✅ ${res.alive} live${res.dead > 0 ? `, ❌ ${res.dead} lỗi` : ''})</span>`;
      } else {
        proxyCheckStatus.innerHTML = `<span style="color: #38bdf8; font-weight: 600;">💾 Đã tải ${res.total} proxy đã lưu từ CSDL.</span>`;
      }
    }
    renderThreadProxyMapping();
  } else if (textareaProxies && textareaProxies.value.trim()) {
    // Migrate existing browser localStorage proxies to DB on first load
    const localLines = textareaProxies.value.split('\n').map(l => l.trim()).filter(l => l.length > 0 && !l.startsWith('#'));
    if (localLines.length > 0 && typeof window.electronAPI.saveProxies === 'function') {
      const type = selectProxyType ? selectProxyType.value : 'http';
      window.electronAPI.saveProxies({ proxies: localLines, type }).catch(() => {});
    }
  }
}

async function reloadAllAppData() {
  try {
    await loadPokedexFromDb();
  } catch (err) {
    console.error('Lỗi khởi tạo pokedex:', err);
  }
  try {
    await loadServers();
  } catch (err) {
    console.error('Lỗi khởi tạo loadServers:', err);
  }
  try {
    await reloadAccounts();
  } catch (err) {
    console.error('Lỗi khởi tạo reloadAccounts:', err);
  }
  try {
    await loadSavedProxiesFromDb();
  } catch (err) {
    console.error('Lỗi khởi tạo loadSavedProxiesFromDb:', err);
  }
}
window.reloadWebAppData = reloadAllAppData;

// Initial bootstrap
(async () => {
  try {
    setupAccountCredentialsUI();
  } catch (err) {
    console.error('Lỗi thiết lập Account Credentials UI:', err);
  }
  try {
    setupMultiThreadingAndProxyUI();
  } catch (err) {
    console.error('Lỗi thiết lập MultiThreading & Proxy UI:', err);
  }
  try {
    updateErrorBadge();
    renderErrorsTable();
    renderThreadProxyMapping();
  } catch (err) {
    console.error('Lỗi khởi tạo UI ban đầu:', err);
  }

  // Wait for Web API config + optional PIN verification before calling protected endpoints
  if (window.electronAPI && typeof window.electronAPI.waitForReady === 'function') {
    const cfg = await window.electronAPI.waitForReady();
    if (cfg && cfg.running) {
      setRunningState(true, 'normal');
    }
  }

  await reloadAllAppData();
})();

// ================= Real-time Thread & Proxy Mapping Preview =================
function getValidProxyList() {
  if (!textareaProxies) return [];
  return textareaProxies.value
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#'));
}

function renderThreadProxyMapping() {
  const container = document.getElementById('thread-mapping-container');
  const badgeStatus = document.getElementById('badge-thread-proxy-status');
  if (!container) return;

  const threads = Math.max(1, parseInt((inputThreads && inputThreads.value) || (inputThreadsRange && inputThreadsRange.value) || 1, 10));
  const isProxyMode = radioNetProxy ? radioNetProxy.checked : false;
  const rawProxies = getValidProxyList();
  const totalProxies = rawProxies.length;

  let proxyAssignedCount = 0;
  let directCount = 0;
  let deadProxyCount = 0;

  let html = '';
  for (let i = 1; i <= threads; i++) {
    const proxyIdx = i - 1;
    if (isProxyMode && totalProxies > 0 && proxyIdx < totalProxies) {
      proxyAssignedCount++;
      const rawP = rawProxies[proxyIdx];
      let displayProxy = rawP;
      const parts = rawP.split(':');
      let shortKey = rawP;
      if (parts.length >= 2) {
        displayProxy = `${parts[0]}:${parts[1]}`;
        shortKey = `${parts[0]}:${parts[1]}`;
      }

      const checkInfo = proxyCheckCache.get(rawP) || proxyCheckCache.get(shortKey);
      let statusDot = 'green';
      let cardClass = 'thread-map-card has-proxy';
      let tagHtml = `<span class="badge-tag-proxy">Proxy #${i}</span>`;
      let titleTooltip = rawP;

      if (checkInfo) {
        if (checkInfo.alive) {
          statusDot = 'green';
          tagHtml = `<span class="badge-tag-proxy tag-alive">Proxy #${i} • ${checkInfo.latency}ms</span>`;
          titleTooltip = `${rawP} (Hoạt động tốt - Ping: ${checkInfo.latency}ms)`;
        } else {
          deadProxyCount++;
          statusDot = 'red';
          cardClass = 'thread-map-card has-proxy has-error';
          tagHtml = `<span class="badge-tag-proxy tag-dead" title="${escapeHtml(checkInfo.error || 'Lỗi kết nối')}">❌ LỖI (${escapeHtml(checkInfo.error || 'Chết')})</span>`;
          titleTooltip = `${rawP} (LỖI: ${checkInfo.error || 'Không kết nối được'})`;
        }
      }

      html += `
        <div class="${cardClass}" title="${escapeHtml(titleTooltip)}">
          <div class="thread-map-left">
            <span class="thread-indicator-dot ${statusDot}"></span>
            <span class="thread-num" style="${statusDot === 'red' ? 'color: #f87171;' : ''}">Luồng #${i}</span>
          </div>
          <div class="thread-arrow">➔</div>
          <div class="thread-map-right">
            <span class="proxy-ip-display" style="${statusDot === 'red' ? 'color: #fca5a5; text-decoration: line-through;' : ''}">${escapeHtml(displayProxy)}</span>
            ${tagHtml}
          </div>
        </div>
      `;
    } else {
      directCount++;
      const isFallback = isProxyMode && totalProxies > 0;
      const tagText = isFallback ? 'Tự động Mạng gốc' : 'Mạng gốc';
      const tooltip = isFallback ? 'Không đủ Proxy, luồng này tự động dùng mạng gốc để tiếp tục' : 'Chạy trực tiếp qua mạng máy chủ';
      html += `
        <div class="thread-map-card is-direct" title="${escapeHtml(tooltip)}">
          <div class="thread-map-left">
            <span class="thread-indicator-dot ${isFallback ? 'amber' : 'blue'}"></span>
            <span class="thread-num">Luồng #${i}</span>
          </div>
          <div class="thread-arrow">➔</div>
          <div class="thread-map-right">
            <span class="proxy-ip-display direct-lbl">🏠 Mạng gốc (Direct IP)</span>
            <span class="badge-tag-direct ${isFallback ? 'tag-amber' : ''}">${tagText}</span>
          </div>
        </div>
      `;
    }
  }

  container.innerHTML = html;

  if (badgeStatus) {
    if (!isProxyMode) {
      badgeStatus.textContent = `${threads} Luồng • 🏠 Mạng gốc`;
      badgeStatus.className = 'badge-tag-opt';
      badgeStatus.style = '';
    } else if (deadProxyCount > 0) {
      badgeStatus.textContent = `⚠️ ${deadProxyCount} Proxy lỗi • ${proxyAssignedCount - deadProxyCount} Hoạt động`;
      badgeStatus.className = 'badge-tag-opt';
      badgeStatus.style.background = 'rgba(239, 68, 68, 0.2)';
      badgeStatus.style.color = '#fca5a5';
      badgeStatus.style.borderColor = 'rgba(239, 68, 68, 0.5)';
    } else if (directCount === 0) {
      badgeStatus.textContent = `${proxyAssignedCount}/${threads} Luồng Proxy (100%)`;
      badgeStatus.className = 'badge-tag-opt badge-green';
      badgeStatus.style = '';
    } else {
      badgeStatus.textContent = `${proxyAssignedCount} Proxy • ${directCount} Mạng gốc`;
      badgeStatus.className = 'badge-tag-opt badge-amber';
      badgeStatus.style = '';
    }
  }
}

if (inputThreadsRange) inputThreadsRange.addEventListener('input', renderThreadProxyMapping);
if (inputThreads) inputThreads.addEventListener('input', renderThreadProxyMapping);
if (radioNetDirect) radioNetDirect.addEventListener('change', renderThreadProxyMapping);
if (radioNetProxy) radioNetProxy.addEventListener('change', renderThreadProxyMapping);
if (textareaProxies) textareaProxies.addEventListener('input', renderThreadProxyMapping);

// ========================================================
// NATURE FILTER CONTROLLER & VIEWPORT-SAFE FLOATING TOOLTIP
// ========================================================
function updateNatureFilterBadge() {
  if (!selectNatureFilter || !badgeNatureCount) return;
  const val = selectNatureFilter.value;
  if (val === 'all') {
    badgeNatureCount.textContent = 'Mọi tính cách';
  } else if (val === 'meta') {
    badgeNatureCount.textContent = '⭐ Chuẩn Meta';
  } else if (/^\d+$/.test(val) && NATURE_MAP[parseInt(val, 10)]) {
    badgeNatureCount.textContent = `⚡ ${NATURE_MAP[parseInt(val, 10)].name}`;
  } else {
    badgeNatureCount.textContent = val;
  }
}

if (selectNatureFilter) {
  updateNatureFilterBadge();
  selectNatureFilter.addEventListener('change', () => {
    safeStorageSet('pokemon_master_nature_filter', selectNatureFilter.value);
    updateNatureFilterBadge();
    currentAccPage = 1;
    renderAccountsTable({ resetScroll: true });
  });
}

const natureTooltip = document.createElement('div');
natureTooltip.className = 'nature-tooltip-card';
natureTooltip.style.display = 'none';
document.body.appendChild(natureTooltip);

function positionNatureTooltip(clientX, clientY) {
  const margin = 12;
  const vw = window.innerWidth;
  const rect = natureTooltip.getBoundingClientRect();
  const w = rect.width || 220;
  const h = rect.height || 80;

  let left = clientX - w / 2;
  if (left < margin) left = margin;
  if (left + w > vw - margin) left = vw - w - margin;

  let top = clientY - h - 14;
  if (top < margin) top = clientY + 18;

  natureTooltip.style.left = `${Math.round(left)}px`;
  natureTooltip.style.top = `${Math.round(top)}px`;
}

document.addEventListener('mouseover', (e) => {
  const pill = e.target.closest('.nature-pill');
  if (!pill) return;
  const title = pill.getAttribute('data-nature-title');
  const buff = pill.getAttribute('data-nature-buff');
  const desc = pill.getAttribute('data-nature-desc');
  if (!title) return;

  natureTooltip.innerHTML = `
    <div style="font-weight: 700; color: #38bdf8; margin-bottom: 4px;">⚡ ${escapeHtml(title)}</div>
    <div style="font-family: monospace; font-size: 11px; color: #4ade80; margin-bottom: 4px; background: rgba(0,0,0,0.35); padding: 2px 6px; border-radius: 4px; display: inline-block;">
      ${escapeHtml(buff || '')}
    </div>
    <div style="font-size: 10.5px; color: #94a3b8; margin-top: 3px;">${escapeHtml(desc || '')}</div>
  `;
  natureTooltip.style.display = 'block';
  positionNatureTooltip(e.clientX, e.clientY);
});

document.addEventListener('mousemove', (e) => {
  if (natureTooltip.style.display !== 'none') {
    positionNatureTooltip(e.clientX, e.clientY);
  }
});

document.addEventListener('mouseout', (e) => {
  const pill = e.target.closest('.nature-pill');
  if (pill) {
    natureTooltip.style.display = 'none';
  }
});

window.addEventListener('scroll', () => {
  if (natureTooltip.style.display !== 'none') {
    natureTooltip.style.display = 'none';
  }
}, true);
