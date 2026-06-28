# Changelog - Notification Service

Tài liệu ghi nhận lịch sử các phiên bản phát triển của hệ thống Notification Service.

---

## [1.1.0] - 2026-06-17
### Added
- Thêm endpoint `/health` hỗ trợ kiểm tra trạng thái hoạt động công khai.
- Tích hợp xác thực **Bearer Token JWT** trên toàn bộ các endpoint nghiệp vụ.
- Hỗ trợ header **`Idempotency-Key`** giúp bảo vệ máy chủ và chống gửi lặp cảnh báo bất đồng bộ.
- Trả về thông báo lỗi chuẩn **Problem JSON (RFC 7807)** cho 400 Bad Request, 401 Unauthorized, 422 Unprocessable Entity, và 500 Internal Server Error.

### Changed
- Cấu trúc lại các endpoint phù hợp 100% với hợp đồng API chính thức (OpenAPI 3.1.0) của nhóm B7.
- Định tuyến `/notifications/trigger` thay thế `/api/v1/alerts`.
- Định tuyến `/notifications/logs` trả về log bọc trong wrapper `items`.
- Cấu hình cổng chạy mặc định sang **`8000`** để giải quyết xung đột tài nguyên local.

---

## [1.0.0] - 2026-06-16
### Added
- Phát triển API FastAPI phục vụ tiếp nhận alert từ Core Business.
- Tích hợp 3 kênh liên kết mạng thật: Telegram Bot, Discord Webhook, và SMTP Mail.
- Thiết lập 2 kênh mock mô phỏng: SMS Mock và Zalo Mock chạy local ghi log.
- Phát triển giao diện Web Dashboard quản trị đẹp mắt với phong cách Glassmorphism.
- Viết tài liệu thiết kế ranh giới (`service_boundary.md`) và danh mục endpoints (`endpoint_catalog.md`).
- Đóng gói container Docker và Docker Compose phục vụ triển khai nhanh.
