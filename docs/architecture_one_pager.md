# Architecture One-Pager - Notification Service

Tài liệu này tóm tắt kiến trúc kỹ thuật của Notification Service, thiết kế dữ liệu, luồng công việc và công nghệ sử dụng.

---

## 1. Tổng quan Hệ thống (System Overview)

Notification Service đóng vai trò là một **dịch vụ trung gian (Broker Service)**. Dịch vụ này tiếp nhận các tín hiệu cảnh báo từ hệ thống lõi **Core Business**, sau đó xử lý kiểm tra trùng lặp để bảo vệ hạ tầng và tự động định tuyến thông báo đến các kênh thích hợp (Telegram, Discord, Email, SMS, Zalo).

```
   ┌───────────────────────────────────────────────────────────┐
   │                       Core Business                       │
   └─────────────────────────────┬─────────────────────────────┘
                                 │ HTTP POST Alert
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │                        API Gateway                        │
   └─────────────────────────────┬─────────────────────────────┘
                                 │ Proxy REST Request
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │             Notification Service (FastAPI)                │
   │                                                           │
   │    ┌─────────────────┐             ┌─────────────────┐    │
   │    │  Deduplication  │             │   Retry Loop    │    │
   │    │   (Memory TTL)  │             │   (Exponential) │    │
   │    └────────┬────────┘             └────────▲────────┘    │
   │             │ Valid                         │ Dispatch    │
   │             └───────────────────────────────┘             │
   └─────────────────────────────┬─────────────────────────────┘
                                 │
         ┌───────────────┬───────┴───────┬───────────────┐
         ▼               ▼               ▼               ▼
    ┌──────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐
    │ Telegram │   │  Discord  │   │   Email   │   │ Zalo/SMS  │
    │ Bot API  │   │  Webhook  │   │ SMTP Svr  │   │   Mock    │
    └──────────┘   └───────────┘   └───────────┘   └───────────┘
```

---

## 2. Các Thành phần Cốt lõi (Core Components)

### 2.1 API Ingest Router (`src/routes/alerts.py`)
Cung cấp các endpoints RESTful để tiếp nhận các yêu cầu gửi tin tức thời. Lớp này chịu trách nhiệm phân tách payload và kiểm tra tính hợp lệ của dữ liệu đầu vào thông qua các Pydantic Schemas.

### 2.2 In-Memory Deduplication Cache (`src/services/notification.py`)
Mỗi khi một `alert_id` được gửi tới, hệ thống kiểm tra sự tồn tại của ID đó trong bộ nhớ RAM tạm thời:
* Mỗi bản ghi lưu kèm theo thời điểm nhận (`timestamp`).
* Định kỳ loại bỏ các bản ghi quá hạn dựa trên tham số cấu hình `DEDUPLICATION_TTL_SECONDS` (mặc định 300 giây).
* Nếu ID đã tồn tại trong khoảng thời gian TTL, yêu cầu gửi sẽ bị loại bỏ ngay lập tức và ghi log trạng thái `duplicate_ignored`.

### 2.3 Resilient Channel Engine (`src/services/notification.py`)
Đóng vai trò là Adapter tích hợp các cổng kết nối ngoại vi:
* **Telegram Adapter**: Tạo HTTP POST payload chứa nội dung định dạng Markdown gửi đến máy chủ Telegram Bot API.
* **Discord Adapter**: Đóng gói thông báo dưới dạng card nhúng Rich Embed với các màu sắc tượng trưng độ nghiêm trọng (Đỏ: High, Vàng: Medium, Xanh: Low) gửi qua Discord Webhook.
* **Email Adapter**: Sử dụng socket SMTP kết nối SSL/TLS bảo mật để chuyển phát thư điện tử.
* **Retry Loop**: Bọc ngoài các Adapter mạng. Khi xảy ra lỗi kết nối mạng (chết kênh, timeout, nghẽn mạng), hệ thống tự động tính toán thời gian chờ trễ lũy thừa (Exponential Backoff): `BaseDelay * 2^(attempt)` và thực hiện gửi lại cho đến khi thành công hoặc chạm giới hạn `RETRY_MAX_LIMIT`.

### 2.4 Dual Logging System (`src/utils/logger.py`)
Sử dụng thư viện `logging` chuẩn của Python tích hợp `RotatingFileHandler` để phân chia luồng ghi log:
1. **Console Stream**: Định dạng tối giản, dễ theo dõi bằng mắt thường.
2. **File Stream (`evidence/logs/notification_service.log`)**: Định dạng JSON nghiêm ngặt. Mỗi dòng log là một bản ghi JSON độc lập. Thiết kế này hỗ trợ các công cụ thu thập log (như Analytics Service) dễ dàng parse và đồng bộ mà không cần phụ thuộc database dùng chung.

---

## 3. Công nghệ Sử dụng (Tech Stack)

* **Ngôn ngữ**: Python 3.10+
* **Framework**: FastAPI (Thiết kế bất đồng bộ, tự động sinh Swagger UI kiểm thử).
* **HTTP Client**: `requests` (Giao tiếp HTTP đồng bộ, tối ưu kết nối mạng).
* **Máy chủ chạy**: Uvicorn ASGI Server.
* **Đóng gói**: Docker & Docker Compose (Giảm thiểu xung đột môi trường).
* **Giao diện quản lý**: HTML5, Vanilla CSS, Vanilla JS.
