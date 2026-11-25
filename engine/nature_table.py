"""
nature_table.py
Pokemon Nature / Personality (Tính cách / 性格) Master Table for Poke Dai Chien
Extracted and reverse-engineered directly from live game engine memory (libHOGame / Scaleform GFx).
Contains all 25 official base natures (1001-1025) and enhanced natures (1026-1050).
"""

from typing import Dict, Any, Optional

NATURE_MAP: Dict[int, Dict[str, Any]] = {
    # ── Tấn công vật lý (+DAM) ──
    1001: {
        "id": 1001,
        "name": "Cô Đơn",
        "en": "Lonely",
        "buff": "DAM+10%",
        "nerf": "DEF-10%",
        "type": "dam",
        "meta": False,
        "desc": "Tăng Tấn công (+10%), giảm Thủ vật lý (-10%)"
    },
    1002: {
        "id": 1002,
        "name": "Cứng",
        "en": "Adamant",
        "buff": "DAM+10%",
        "nerf": "CRIT-10%",
        "type": "dam",
        "meta": True,
        "desc": "Tăng Tấn công (+10%), giảm Đặc công (-10%) [Chuẩn Meta Vật lý]"
    },
    1003: {
        "id": 1003,
        "name": "Nghịch",
        "en": "Naughty",
        "buff": "DAM+10%",
        "nerf": "ARM-10%",
        "type": "dam",
        "meta": False,
        "desc": "Tăng Tấn công (+10%), giảm Kháng phép (-10%)"
    },
    1004: {
        "id": 1004,
        "name": "Dũng",
        "en": "Brave",
        "buff": "DAM+10%",
        "nerf": "SPEED-10%",
        "type": "dam",
        "meta": False,
        "desc": "Tăng Tấn công (+10%), giảm Tốc độ (-10%)"
    },

    # ── Thủ vật lý (+DEF) ──
    1005: {
        "id": 1005,
        "name": "Gan Dạ",
        "en": "Bold",
        "buff": "DEF+10%",
        "nerf": "DAM-10%",
        "type": "def",
        "meta": True,
        "desc": "Tăng Thủ vật lý (+10%), giảm Tấn công (-10%) [Chuẩn Meta Tanker Phép]"
    },
    1006: {
        "id": 1006,
        "name": "Bướng",
        "en": "Impish",
        "buff": "DEF+10%",
        "nerf": "CRIT-10%",
        "type": "def",
        "meta": True,
        "desc": "Tăng Thủ vật lý (+10%), giảm Đặc công (-10%) [Chuẩn Meta Tanker Vật lý]"
    },
    1007: {
        "id": 1007,
        "name": "Vô Tư",
        "en": "Lax",
        "buff": "DEF+10%",
        "nerf": "ARM-10%",
        "type": "def",
        "meta": False,
        "desc": "Tăng Thủ vật lý (+10%), giảm Kháng phép (-10%)"
    },
    1008: {
        "id": 1008,
        "name": "Nhàn",
        "en": "Relaxed",
        "buff": "DEF+10%",
        "nerf": "SPEED-10%",
        "type": "def",
        "meta": False,
        "desc": "Tăng Thủ vật lý (+10%), giảm Tốc độ (-10%)"
    },

    # ── Tấn công phép / Đặc công (+CRIT) ──
    1009: {
        "id": 1009,
        "name": "Bảo Thủ",
        "en": "Modest",
        "buff": "CRIT+10%",
        "nerf": "DAM-10%",
        "type": "crit",
        "meta": True,
        "desc": "Tăng Đặc công (+10%), giảm Tấn công (-10%) [Chuẩn Meta Công Phép]"
    },
    1010: {
        "id": 1010,
        "name": "Vững",
        "en": "Mild",
        "buff": "CRIT+10%",
        "nerf": "DEF-10%",
        "type": "crit",
        "meta": False,
        "desc": "Tăng Đặc công (+10%), giảm Thủ vật lý (-10%)"
    },
    1011: {
        "id": 1011,
        "name": "Vô Tâm",
        "en": "Rash",
        "buff": "CRIT+10%",
        "nerf": "ARM-10%",
        "type": "crit",
        "meta": False,
        "desc": "Tăng Đặc công (+10%), giảm Kháng phép (-10%)"
    },
    1012: {
        "id": 1012,
        "name": "Im",
        "en": "Quiet",
        "buff": "CRIT+10%",
        "nerf": "SPEED-10%",
        "type": "crit",
        "meta": False,
        "desc": "Tăng Đặc công (+10%), giảm Tốc độ (-10%)"
    },

    # ── Thủ phép / Kháng phép (+ARM) ──
    1013: {
        "id": 1013,
        "name": "Trầm",
        "en": "Calm",
        "buff": "ARM+10%",
        "nerf": "DAM-10%",
        "type": "arm",
        "meta": True,
        "desc": "Tăng Kháng phép (+10%), giảm Tấn công (-10%) [Chuẩn Meta Kháng Phép]"
    },
    1014: {
        "id": 1014,
        "name": "Ngoan",
        "en": "Gentle",
        "buff": "ARM+10%",
        "nerf": "DEF-10%",
        "type": "arm",
        "meta": False,
        "desc": "Tăng Kháng phép (+10%), giảm Thủ vật lý (-10%)"
    },
    1015: {
        "id": 1015,
        "name": "Cẩn Thận",
        "en": "Careful",
        "buff": "ARM+10%",
        "nerf": "CRIT-10%",
        "type": "arm",
        "meta": True,
        "desc": "Tăng Kháng phép (+10%), giảm Đặc công (-10%) [Chuẩn Meta Kháng Phép Vật Lý]"
    },
    1016: {
        "id": 1016,
        "name": "Ngạo",
        "en": "Sassy",
        "buff": "ARM+10%",
        "nerf": "SPEED-10%",
        "type": "arm",
        "meta": False,
        "desc": "Tăng Kháng phép (+10%), giảm Tốc độ (-10%)"
    },

    # ── Tốc độ (+SPEED) ──
    1017: {
        "id": 1017,
        "name": "Nhát",
        "en": "Timid",
        "buff": "SPEED+10%",
        "nerf": "DAM-10%",
        "type": "speed",
        "meta": True,
        "desc": "Tăng Tốc độ (+10%), giảm Tấn công (-10%) [Chuẩn Meta Nhanh Phép]"
    },
    1018: {
        "id": 1018,
        "name": "Nóng",
        "en": "Hasty",
        "buff": "SPEED+10%",
        "nerf": "DEF-10%",
        "type": "speed",
        "meta": False,
        "desc": "Tăng Tốc độ (+10%), giảm Thủ vật lý (-10%)"
    },
    1019: {
        "id": 1019,
        "name": "Cởi Mở",
        "en": "Jolly",
        "buff": "SPEED+10%",
        "nerf": "CRIT-10%",
        "type": "speed",
        "meta": True,
        "desc": "Tăng Tốc độ (+10%), giảm Đặc công (-10%) [Chuẩn Meta Nhanh Vật Lý]"
    },
    1020: {
        "id": 1020,
        "name": "Ngây Thơ",
        "en": "Naive",
        "buff": "SPEED+10%",
        "nerf": "ARM-10%",
        "type": "speed",
        "meta": False,
        "desc": "Tăng Tốc độ (+10%), giảm Kháng phép (-10%)"
    },

    # ── Cân bằng (Neutral) ──
    1021: {
        "id": 1021,
        "name": "Ngại",
        "en": "Bashful",
        "buff": "",
        "nerf": "",
        "type": "neutral",
        "meta": False,
        "desc": "Cân bằng, không tăng giảm chỉ số"
    },
    1022: {
        "id": 1022,
        "name": "Thật",
        "en": "Docile",
        "buff": "",
        "nerf": "",
        "type": "neutral",
        "meta": False,
        "desc": "Cân bằng, không tăng giảm chỉ số"
    },
    1023: {
        "id": 1023,
        "name": "Thẳng",
        "en": "Hardy",
        "buff": "",
        "nerf": "",
        "type": "neutral",
        "meta": False,
        "desc": "Cân bằng, không tăng giảm chỉ số"
    },
    1024: {
        "id": 1024,
        "name": "Xốc Nổi",
        "en": "Quirky",
        "buff": "",
        "nerf": "",
        "type": "neutral",
        "meta": False,
        "desc": "Cân bằng, không tăng giảm chỉ số"
    },
    1025: {
        "id": 1025,
        "name": "Nghiêm",
        "en": "Serious",
        "buff": "",
        "nerf": "",
        "type": "neutral",
        "meta": False,
        "desc": "Cân bằng, không tăng giảm chỉ số"
    }
}

# Auto-generate Enhanced Natures (1026-1050)
for base_id in range(1001, 1026):
    base_info = NATURE_MAP[base_id]
    enh_id = base_id + 25
    buff_enh = base_info["buff"].replace("10%", "20%") if base_info["buff"] else ""
    nerf_enh = base_info["nerf"].replace("10%", "10%") if base_info["nerf"] else ""
    NATURE_MAP[enh_id] = {
        "id": enh_id,
        "name": f"Rất {base_info['name']}",
        "en": f"Very {base_info['en']}",
        "buff": buff_enh,
        "nerf": nerf_enh,
        "type": base_info["type"],
        "meta": base_info["meta"],
        "desc": f"Tính cách tiến cấp: {base_info['desc']}"
    }


def get_nature_info(xingge_id: int) -> Dict[str, Any]:
    """Retrieve nature information by XingGeID"""
    try:
        xid = int(xingge_id)
    except (ValueError, TypeError):
        xid = 0

    if xid in NATURE_MAP:
        return NATURE_MAP[xid]
    
    return {
        "id": xid,
        "name": "Chưa rõ",
        "en": "Unknown",
        "buff": "",
        "nerf": "",
        "type": "neutral",
        "meta": False,
        "desc": "Tính cách chưa xác định"
    }
