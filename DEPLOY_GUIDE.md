# 🚀 Hướng dẫn Chạy Local & Deploy Pokemon Auto Register Web

Ứng dụng Web độc lập chạy được trên **máy tính (Windows/Linux)** và deploy miễn phí lên **Render + Supabase**, truy cập mượt trên cả **PC, Tablet và Điện thoại**.

---

## 1. Chạy thử ngay trên máy (Local — Không cần Supabase)

Mặc định nếu chưa cấu hình `SUPABASE_URL`/`SUPABASE_KEY`, app tự động dùng **SQLite cục bộ** tại `data/pokemon_web.db` (đã tích hợp sẵn 1.962 server + 898 Pokédex).

```bash
cd auto_register_web
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Mở trình duyệt tại: **http://localhost:8000**

> **Tùy chọn đặt mã PIN bảo vệ:**
> Tạo file `.env` từ `.env.example` và điền `ACCESS_PIN=123456` (không commit file `.env` lên Git!).

---

## 2. Thiết lập Database vĩnh viễn với Supabase (Khuyên dùng khi deploy Render)

Render Free có ổ cứng tạm (reset sau mỗi lần restart/redeploy). Kết nối **Supabase** giúp lưu toàn bộ tài khoản an toàn, không bao giờ mất dữ liệu và chịu tải mượt 50+ luồng song song.

### Cách 1 (Nhanh nhất — Dùng trực tiếp chuỗi `DATABASE_URL` Pooler):
1. Copy file `.env.example` thành `.env` (hoặc cấu hình trong tab **Environment** trên Render).
2. Điền chuỗi **Transaction Pooler (port 6543)** của bạn vào biến `DATABASE_URL` (nhớ thay `[YOUR-DATABASE-PASSWORD]` bằng mật khẩu database thực tế của bạn — **không** commit file `.env` lên Git):
   ```env
   DATABASE_URL=postgresql://postgres.tmyznmuqopkhyqycnequ:<MAT_KHAU_DB>@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres
   ```
3. Khởi động server — backend sẽ **tự động tạo sẵn** toàn bộ bảng `accounts`, `servers`, `pokedex`, `app_settings` và các index trên Supabase (kết nối SSL `sslmode=require` + connection pool 10 kết nối an toàn cho 50 luồng).

### Cách 2 (Thay thế — Dùng Supabase REST API):
Nếu không dùng `DATABASE_URL`, bạn có thể chạy file `supabase_schema.sql` trong **Supabase SQL Editor** rồi điền `SUPABASE_URL` và `service_role` key vào `SUPABASE_KEY`.

---

## 3. Deploy 1-Click lên Render

1. Push thư mục `auto_register_web` lên repository GitHub của bạn (có thể để làm root repo hoặc chọn Root Directory là `auto_register_web`).
2. Vào [dashboard.render.com](https://dashboard.render.com) -> **New +** -> **Blueprint** (hoặc **Web Service** chọn Runtime **Docker**).
3. Render sẽ tự đọc `render.yaml` và `Dockerfile` (Health Check Path: `/health`).
4. Trong tab **Environment**, thêm các biến môi trường:
   - `DATABASE_URL`: Chuỗi kết nối Supabase Transaction Pooler (`postgresql://postgres.tmyznmuqopkhyqycnequ:<MAT_KHAU_DB>@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres`)
   - `ACCESS_PIN`: *(Khuyên dùng)* Mã PIN bảo vệ trang web khi mở public (ví dụ: `889900`)
5. Bấm **Deploy** và đợi 2-3 phút. Truy cập `https://<ten-app>.onrender.com/health` thấy `{"status":"ok","storage":"supabase",...}` là thành công!

---

## 4. Giữ Server thức 24/7 với UptimeRobot (Miễn phí)

Render Free sẽ ngủ sau 15 phút không có request. Dùng UptimeRobot để ping nhẹ `/health` mỗi 5 phút:

1. Đăng ký miễn phí tại [uptimerobot.com](https://uptimerobot.com).
2. Bấm **Add New Monitor**:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Pokemon Auto Register Web`
   - **URL**: `https://<ten-app>.onrender.com/health`
   - **Monitoring Interval**: `5 minutes`
3. Lưu lại — UptimeRobot sẽ giữ container luôn sẵn sàng để mở từ điện thoại bất kỳ lúc nào.

---

## 5. Kiểm tra nhanh API

| Endpoint | Mô tả |
|---|---|
| `GET /health` | Kiểm tra trạng thái server & storage (dùng cho Render / UptimeRobot) |
| `GET /api/config/status` | Trạng thái `storage` (`supabase`/`sqlite`), `running`, `pin_required` |
| `POST /api/auth/verify` | Xác thực mã PIN (`{"pin": "..."}`) |
| `WS /ws` | WebSocket realtime log, trạng thái task, danh sách acc & server mới |
