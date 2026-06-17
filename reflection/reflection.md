# Báo Cáo Tự Đánh Giá (Self Reflection)

Tài liệu ghi lại quá trình tự đánh giá dự án Notification Service, các bài học rút ra và hướng phát triển trong tương lai.

---

## 1. Những kết quả đạt được (Key Accomplishments)

* **Thiết kế ranh giới dịch vụ rõ ràng**: Dịch vụ đóng vai trò là một broker trung gian, tách biệt hoàn toàn logic kinh doanh phát hiện sự kiện lạ (của Core Business) và logic phân tích log (của Analytics).
* **Đa dạng hóa kênh gửi thông báo**: Tích hợp thành công cả 3 kênh kết nối mạng thực tế (Telegram Bot API, Discord Webhook, SMTP Email) cùng 2 kênh mô phỏng (Zalo Mock, SMS Mock) hoạt động mượt mà.
* **Xây dựng Dashboard trực quan và hiện đại**: Dashboard được xây dựng bằng Vanilla HTML/CSS/JS với phong cách Glassmorphism sang trọng, hỗ trợ mô phỏng bắn alert, bật tắt chế độ Mock/Real linh hoạt và hiển thị biểu đồ thống kê theo thời gian thực (polling 4s).
* **Cơ chế chống spam và lỗi mạng ổn định**: Tích hợp bộ đệm deduplication trượt trong bộ nhớ tránh gửi trùng cảnh báo và vòng lặp thử lại có trễ lũy thừa (Exponential Backoff Retry) giúp ứng dụng phục hồi trước các lỗi mạng tạm thời.

---

## 2. Thách thức gặp phải và Giải pháp (Challenges & Solutions)

* **Thách thức về SMTP kết nối email**: Khi thử kết nối SMTP Gmail thật, Google yêu cầu mật khẩu ứng dụng (App Password) và kết nối TLS/SSL thường xuyên bị chặn hoặc từ chối kết nối nếu cấu hình cổng sai.
  * *Giải pháp*: Cung cấp hướng dẫn rõ ràng trong file `.env` về cách tạo mật khẩu ứng dụng Gmail và bổ sung cơ chế tự động chuyển đổi giữa cổng `465` (SSL) và `587` (TLS) trong mã nguồn Python.
* **Kiểm thử bất đồng bộ mà không có Database**: Yêu cầu dự án ghi log cho Analytics mà không được thiết lập hệ quản trị cơ sở dữ liệu lớn cồng kềnh.
  * *Giải pháp*: Sử dụng hệ thống ghi log luồng đôi (Dual Logging) ra tệp tin JSON tĩnh. Điều này vừa giúp lưu trữ dữ liệu dạng text nhẹ, vừa giúp Analytics Service có thể kéo dữ liệu dễ dàng qua HTTP API hoặc qua log shippers.

---

## 3. Định hướng cải tiến (Future Improvements)

* **Persistent Storage**: Sử dụng cơ sở dữ liệu siêu nhẹ SQLite để lưu cache deduplication và logs thay vì dùng memory, giúp thông tin không bị mất đi khi khởi động lại server/container.
* **Xác thực API (Security)**: Bổ sung OAuth2 hoặc API Key header validation cho endpoint `POST /api/v1/alerts` để đảm bảo chỉ có Core Business được quyền phát tín hiệu cảnh báo trong mạng nội bộ.
* **Template hóa tin nhắn**: Cho phép người dùng tùy chỉnh template tin nhắn cho từng kênh khác nhau trực tiếp trên giao diện Dashboard thay vì code cứng định dạng Markdown/HTML trong service.
