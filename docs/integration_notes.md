# Hướng Dẫn Tích Hợp (Integration Notes)

Tài liệu này cung cấp chỉ dẫn kỹ thuật chi tiết để tích hợp Notification Service với các dịch vụ khác trong hệ thống chung (Core Business, Analytics Service, API Gateway).

---

## 1. Tích hợp với Core Business (Upstream)

Core Business là nơi phát hiện các bất thường (ví dụ: phát hiện xâm nhập, lỗi phần cứng, quá tải tài nguyên) và cần đẩy cảnh báo ngay lập tức.

### Cách thức tích hợp:
* **Giao thức**: HTTP POST.
* **Endpoint**: `http://<notification-service-ip>:8085/api/v1/alerts` (Hoặc qua URL của API Gateway).
* **Payload cấu trúc đề nghị**:
```json
{
  "alert_id": "ALT-001",
  "severity": "high",
  "message": "Nội dung thông báo lỗi cụ thể",
  "target": "security_team",
  "channels": ["telegram"]
}
```

### Lưu ý quan trọng cho Core Business:
1. **Thiết lập `alert_id`**: Mỗi sự kiện lạ phát hiện phải được gán một `alert_id` duy nhất (Ví dụ: `UUID` hoặc mã có quy tắc tăng dần kèm tiền tố). Tránh gửi trùng `alert_id` cho 2 sự kiện khác nhau vì cơ chế Deduplication của Notification Service sẽ chặn lại.
2. **Xử lý Response**: 
   * Nếu nhận được phản hồi chứa `"status": "duplicate_ignored"`, điều này nghĩa là hệ thống Notification Service đã nhận được tin nhắn này gần đây và bỏ qua để tránh spam. Core Business không cần làm gì thêm.
   * Nếu nhận được phản hồi có `"status": "delivered"`, tin nhắn đã gửi thành công tới người nhận.

---

## 2. Tích hợp với Analytics Service (Downstream)

Analytics Service cần thu thập toàn bộ log trạng thái gửi tin để phân tích, đo lường hiệu suất hoặc vẽ biểu đồ quản trị.

### Có hai cách tích hợp:

#### Phương án A: Tích hợp qua API (Pull Mode)
Analytics Service định kỳ (ví dụ: mỗi 5 phút) gọi API:
* **Endpoint**: `GET http://<notification-service-ip>:8085/api/v1/alerts/logs`
* **Query Params**: Có thể lọc theo thời gian hoặc số lượng bằng `limit` (tối đa 100 log/request).

#### Phương án B: Đọc trực tiếp File Log (Shared Volume / Log Shipper) - KHUYẾN NGHỊ
Vì Notification Service ghi log ra file dạng JSON dòng (JSON lines) tại đường dẫn `/app/evidence/logs/notification_service.log`, Analytics Service có thể cấu hình mount chung thư mục này hoặc sử dụng Logstash / Fluent Bit để thu gom tự động:
* **Cấu trúc mỗi dòng log**:
```json
{"timestamp": "2026-06-17 00:31:02", "level": "INFO", "module": "notification", "message": {"alert_id": "ALT-001", "severity": "high", "message": "Unknown person detected near main gate", "target": "security_team", "channel": "telegram", "sent": true, "status": "delivered", "retry_count": 0, "error": "", "timestamp": "2026-06-17 00:31:02"}}
```
Việc parse log file sẽ tránh làm ảnh hưởng hiệu năng xử lý HTTP chính của Notification Service.

---

## 3. Tích hợp với API Gateway

Nếu hệ thống sử dụng một API Gateway chung (ví dụ: Kong, Nginx, Ocelot) để định tuyến yêu cầu từ bên ngoài:

* Cấu hình định tuyến tất cả các request có tiền tố `/api/v1/alerts` và `/api/v1/channels` chuyển tiếp đến địa chỉ IP nội bộ của container Notification Service ở cổng `8085`.
* Cho phép cors header nếu các service front-end khác muốn gọi API trực tiếp.
