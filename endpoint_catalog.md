# Endpoint Catalog - Notification Service

Tài liệu này mô tả danh mục các điểm cuối (Endpoints) API chính thức khớp với OpenAPI Contract của Notification Service.

---

## 1. GET `/health`

Kiểm tra trạng thái hoạt động của Notification Service.

* **Security**: Không yêu cầu Bearer Token.
* **Content-Type**: `application/json`
* **Response `200`**:
  ```json
  {
    "status": "ok",
    "service": "notification-service",
    "time": "2026-05-10T08:00:00Z"
  }
  ```

---

## 2. POST `/notifications/trigger`

Tiếp nhận alert từ Core Business (Nhóm B6) và xử lý đưa vào hàng đợi phân phối bất đồng bộ.

* **Security**: Yêu cầu Bearer Token (`Authorization: Bearer <JWT_TOKEN>`).
* **Headers**:
  * `Idempotency-Key` (String, tùy chọn): Khóa chống trùng lặp gửi tin. Nếu gửi trùng khóa trong khoảng thời gian TTL, hệ thống trả về kết quả đã xử lý trước đó mà không gửi lại.
* **Content-Type**: `application/json`
* **Request Body**:
  | Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
  | :--- | :--- | :--- | :--- |
  | `alert_id` | String | Có | Định danh UUID của alert truyền từ Core Business |
  | `severity` | String | Có | Mức độ nghiêm trọng (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
  | `message` | String | Có | Nội dung thông tin cảnh báo chi tiết (5 - 500 ký tự) |
  | `target` | String | Có | Nhóm chức năng tiếp nhận (ví dụ: `security_team`) |
  | `channels` | Array[String] | Không | Tùy chọn các kênh gửi (`telegram`, `email`, `discord`, `zalo`, `sms`, `log`) |

### Ví dụ Request Payload
```json
{
  "alert_id": "0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
  "severity": "HIGH",
  "message": "Phát hiện truy cập trái phép tại cổng chính",
  "target": "security_team",
  "channels": ["telegram", "email"]
}
```

### Ví dụ Response `202` (Đã tiếp nhận)
```json
{
  "sent": true,
  "channel": "telegram",
  "status": "delivered",
  "ticket_id": "0196fb3e-5ba2-7e2f-8a11-6d7249e3cade"
}
```

### Lỗi thường gặp:
* **401 Unauthorized**: Header thiếu Bearer Token hoặc token sai định dạng.
* **400 Bad Request**: Định dạng payload không hợp lệ (mất các trường bắt buộc, message quá ngắn...).
* **422 Unprocessable Entity**: Lỗi logic nghiệp vụ (ví dụ: target rỗng).

---

## 3. GET `/notifications/logs`

Truy cập nhật ký gửi tin phục vụ đồng bộ Analytics hoặc Dashboard hiển thị.

* **Security**: Yêu cầu Bearer Token (`Authorization: Bearer <JWT_TOKEN>`).
* **Query Parameters**:
  * `alert_id` (String, tùy chọn): Lọc theo mã alert.
  * `channel` (String, tùy chọn): Lọc theo kênh (`telegram`, `email`, `discord`, `zalo`, `sms`).
* **Response `200`**:
  ```json
  {
    "items": [
      {
        "ticket_id": "0196fb3e-5ba2-7e2f-8a11-6d7249e3cade",
        "alert_id": "0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
        "channel": "telegram",
        "target": "security_team",
        "status": "delivered",
        "retry_count": 0,
        "error_message": null,
        "timestamp": "2026-06-17T00:31:02Z"
      }
    ]
  }
  ```

---

## 4. GET/POST `/api/v1/channels` & `/configure`

*(Endpoints nội bộ phục vụ cấu hình Dashboard quản trị)*

* Xem trạng thái cấu hình và chỉnh sửa tham số của từng kênh (Mock/Real, key, token).
