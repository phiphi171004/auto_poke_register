# auto_poke_register

Ứng dụng Web tự động đăng ký tài khoản, chọn server, tạo nhân vật, nhận 20 vé web và mở Pokédex cho Pokémon H5.
Hỗ trợ chạy đa luồng cực nhanh (lên tới 50 luồng), tự động đồng bộ Database PostgreSQL / Supabase, quản lý Proxy và giao diện Web Responsive trực quan trên cả máy tính lẫn điện thoại.

---

## 🌟 Tính Năng Nổi Bật

- **Giao diện Web Hiện Đại & Responsive**: Thiết kế tối ưu cho cả Desktop, Tablet và Mobile.
- **Hỗ trợ Đa Luồng Linh Hoạt**: Cấu hình từ 1 đến 50 luồng đồng thời theo cấu hình máy chủ.
- **Quản lý & Kiểm tra Proxy**:
  - Nhập danh sách proxy HTTP / SOCKS5.
  - Tự động test live, đo latency (ms), tự động lưu trạng thái vào cơ sở dữ liệu.
  - Xoay vòng proxy thông minh theo luồng.
- **Quy trình Tự động Đầy đủ (5 Bước)**:
  1. Đăng ký tài khoản (hỗ trợ random prefix hoặc custom).
  2. Đăng nhập hệ thống & lấy session game.
  3. Chọn server & tạo nhân vật theo tên ngẫu nhiên.
  4. Mở Pokédex và quay tướng tân thủ.
  5. Tự động nhận 20 vé web sự kiện (kèm cơ chế polling và backoff chống nghẽn server).
- **Lưu trữ Đám mây (Supabase / PostgreSQL)**:
  - Tự động tạo bảng và lưu trữ tài khoản, nhân vật, Pokémon quay được, cấu hình và danh sách proxy.
  - Tự động fallback sang SQLite nội bộ nếu không cấu hình Supabase.
- **Sẵn sàng Triển khai Render**: Đi kèm `render.yaml`, `Dockerfile`, cấu hình Health check và hướng dẫn chi tiết.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Cục Bộ

### 1. Yêu cầu Hệ thống
- Python 3.10 trở lên.
- Đã cài đặt `pip`.

### 2. Cài đặt Thư viện
```bash
pip install -r requirements.txt
```

### 3. Cấu hình Biến Môi trường (Tùy chọn)
Tạo file `.env` từ `.env.example`:
```ini
PORT=8000
DATABASE_URL=postgresql://user:password@host:6543/postgres
```
*Nếu không đặt `DATABASE_URL`, ứng dụng sẽ tự động lưu vào SQLite tại `data/accounts.db`.*

### 4. Khởi chạy Ứng dụng
```bash
python server/app.py
```
Mở trình duyệt truy cập: `http://localhost:8000`

---

## ☁️ Triển Khai Lên Render (Render.com)

1. Tạo **Web Service** mới trên Render từ repository GitHub này.
2. Chọn loại môi trường: **Docker** hoặc **Python 3**.
   - **Docker**: Render sẽ tự động build theo `Dockerfile` đã có sẵn.
   - **Python**:
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `uvicorn server.app:app --host 0.0.0.0 --port $PORT`
3. Cấu hình **Environment Variables**:
   - `DATABASE_URL`: Chuỗi kết nối Supabase Pooler (`postgresql://...:6543/postgres`).
   - `PORT`: `8000` (Render tự gán cổng này).
4. Khuyến nghị cấu hình gói:
   - Chạy 10 - 20 luồng: Gói Starter ($7/tháng, 0.5 CPU, 512MB RAM) hoặc Free.
   - Chạy 50 luồng đồng thời: Gói Standard ($25/tháng, 1 CPU, 2GB RAM).

---

## 📁 Cấu Trúc Dự Án

```
auto_register_web/
├── data/                    # Thư mục lưu trữ database SQLite & runtime log cục bộ
├── engine/                  # Core logic game (login, register, character, claim, pokedex)
│   ├── activity_claim_client.py
│   ├── auto_reg.py
│   ├── captcha_solver.py
│   ├── pokedex_parser.py
│   └── ...
├── frontend/                # Giao diện người dùng Web Responsive (HTML/CSS/JS)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── server/                  # Backend FastAPI & WebSockets
│   ├── app.py               # REST API & WebSocket event streaming
│   ├── storage.py           # Quản lý Database (Supabase PostgreSQL / SQLite fallback)
│   └── task_runner.py       # Quản lý worker đa luồng bất đồng bộ
├── Dockerfile               # File build container Docker cho Render / Cloud
├── render.yaml              # Render Blueprint
├── requirements.txt         # Danh sách package Python
└── supabase_schema.sql      # Schema khởi tạo các bảng Supabase
```

---

## 🔒 Bản quyền & Miễn trừ Trách nhiệm
Mã nguồn phục vụ mục đích học tập, nghiên cứu tự động hóa giao thức HTTP/WebSocket và phát triển giao diện Web.
