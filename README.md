# Notification Service (Dịch vụ gửi thông báo sự kiện bất thường)

Dự án này là thành phần **Notification Service** thuộc đồ án môn học **FIT4110: Dịch vụ kết nối và công nghệ nền tảng**.

---

## 1. Tên Service
* **Tên chính thức**: `Notification Service`
* **Định danh trong hệ thống**: `notification-service`

## 2. Vai Trò của Service trong Hệ Thống
Notification Service đóng vai trò là một dịch vụ trung gian chuyên biệt chịu trách nhiệm:
1. Nhận các sự kiện cảnh báo (Alert) từ module nghiệp vụ chính (**Core Business**) hoặc qua **API Gateway** khi phát hiện hoạt động bất thường (ví dụ: phát hiện xâm nhập, nhiệt độ phòng máy tăng cao, rò rỉ khí).
2. Xử lý logic lọc trùng (Deduplication) để tránh gây nhiễu/spam cho người vận hành.
3. Chuyển tiếp và phân phối cảnh báo tức thời tới các kênh thông báo đích thích hợp (Telegram, Discord, Email, SMS, Zalo).
4. Lưu trữ lịch sử và trạng thái gửi dưới dạng log file có cấu trúc để cung cấp cho **Analytics Service** tiến hành đo lường hiệu năng.

## 3. Thành Viên Nhóm
| Họ và Tên | Mã số sinh viên | Vai trò đóng góp |
| :--- | :--- | :--- |
| [Nguyễn Văn A] | [SV123456] | Thiết kế Kiến trúc Backend & Tích hợp Kênh |
| [Trần Thị B] | [SV654321] | Xây dựng Dashboard Quản trị & CSS Styles |
| [Lê Hoàng C] | [SV789012] | Đóng gói Docker, Postman Tests & Viết Tài liệu |

## 4. Công Nghệ Sử Dụng
* **Mã nguồn**: Python 3.10+
* **Web Framework**: FastAPI & Uvicorn (ASGI)
* **Giao diện Web Dashboard**: HTML5, Vanilla CSS (Thiết kế Glassmorphism), Vanilla Javascript
* **Tích hợp kênh ngoại vi**: `smtplib` (Email SSL/TLS), `requests` (Telegram Bot API & Discord Webhook)
* **Containerization**: Docker & Docker Compose
* **API Spec**: OpenAPI 3.0 (Swagger UI tự động sinh tại `/docs`)

## 5. Cách Chạy Local
Vui lòng xem chi tiết hướng dẫn tại file [RUN_LOCAL.md](RUN_LOCAL.md).

Tóm tắt các lệnh chính:
```bash
# 1. Tạo và kích hoạt môi trường ảo
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell

# 2. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

# 3. Khởi chạy server FastAPI
python src/main.py
```
Sau đó truy cập Dashboard tại: [http://localhost:8086](http://localhost:8086)

## 6. Cách Chạy Bằng Docker
Notification Service được đóng gói sẵn Docker để dễ dàng triển khai.

### Yêu cầu:
* Đã cài đặt Docker và Docker Compose trên máy tính.

### Các bước khởi chạy:
1. Mở terminal tại thư mục gốc `Notify_app`.
2. Tạo file cấu hình `.env` từ `.env.example` (Mặc định chế độ Mock đã được bật sẵn để chạy offline không cần API Key):
   ```bash
   cp .env.example .env
   ```
3. Chạy lệnh xây dựng và khởi động container:
   ```bash
   docker compose up --build -d
   ```
4. Truy cập giao diện kiểm thử của container tại địa chỉ: [http://localhost:8086](http://localhost:8086).
5. Để dừng dịch vụ, chạy lệnh:
   ```bash
   docker compose down
   ```

## 7. Danh Sách Endpoint Chính
* **POST** `/api/v1/alerts`: Nhận cảnh báo từ Core Business.
* **GET** `/api/v1/alerts/logs`: Trả về danh sách log cảnh báo (phục vụ Analytics).
* **GET** `/api/v1/channels`: Lấy danh sách và trạng thái các kênh kết nối.
* **POST** `/api/v1/channels/configure`: Cập nhật cấu hình cổng kết nối động.
* **GET** `/docs`: Giao diện Swagger UI tài liệu API chi tiết.

Để biết chi tiết cấu trúc Request/Response, vui lòng tham khảo [endpoint_catalog.md](endpoint_catalog.md).

## 8. Service Upstream / Downstream
```
   [Core Business] ────────► [API Gateway] ────────► [Notification Service]
                                                               │
                                         ┌─────────────────────┼─────────────────────┐
                                         ▼                     ▼                     ▼
                                 [Telegram API]        [Discord Webhook]     [Analytics Service]
```
* **Upstream (Các dịch vụ gọi tới)**: Core Business, API Gateway.
* **Downstream (Các dịch vụ nhận tin)**: Analytics Service (Nhận dữ liệu Log file), các dịch vụ thông báo thứ ba (Telegram Bot API, Discord Webhook, SMTP Mail Server).

## 9. Hướng Dẫn Chạy Test (Postman)
Thư mục `tests/` chứa file Postman Collection giúp giảng viên và các nhóm khác có thể chạy kiểm thử tự động.

1. Khởi chạy Notification Service (Local hoặc Docker) ở cổng `8086`.
2. Mở ứng dụng Postman.
3. Import file Collection [postman_collection.json](tests/postman_collection.json) và Environment [environment_local.json](tests/environment_local.json) từ thư mục `tests/`.
4. Chọn môi trường `Local Environment` trong Postman.
5. Nhấn **Run Collection** để chạy toàn bộ 5 testcase tự động (Kiểm tra gửi tin, chặn trùng lặp, cập nhật cấu hình và truy vấn log).

## 10. Minh Chứng Demo (Screenshots & Video)
* **Video Demo**: Link xem video giới thiệu chi tiết luồng vận hành nằm tại [demo_video_link.txt](evidence/demo_video_link.txt).
* **Hình ảnh chụp Dashboard và Logs**:
  * Các ảnh chụp màn hình minh chứng chức năng được lưu tại thư mục [evidence/screenshots/](file:///f:/Notify_app/evidence/screenshots/).
