import json
from src.utils.database import db_manager

def main():
    print("\n" + "=" * 90)
    print("                      DỮ LIỆU CSDL POSTGRESQL (LATEST RECORDS)")
    print("=" * 90)
    
    # 1. Query inbound_signals
    print("\n[1] BẢNG inbound_signals (Các tín hiệu nhận từ B6)")
    print("-" * 90)
    query_inbound = "SELECT id, log_type, timestamp, status, reason FROM inbound_signals ORDER BY id DESC LIMIT 5;"
    rows_inbound = db_manager.execute_read(query_inbound)
    if not rows_inbound:
        print("  (Chưa có bản ghi nào)")
    else:
        print(f"{'ID':<4} | {'Log Type':<12} | {'Timestamp':<25} | {'Status':<12} | {'Reason'}")
        print("-" * 90)
        for r in rows_inbound:
            print(f"{r['id']:<4} | {r['log_type']:<12} | {r['timestamp']:<25} | {r['status']:<12} | {r['reason']}")
            
    # 2. Query notification_logs
    print("\n[2] BẢNG notification_logs (Nhật ký gửi thông báo đi các kênh)")
    print("-" * 90)
    query_logs = "SELECT ticket_id, channel, status, severity, timestamp, message FROM notification_logs ORDER BY timestamp DESC LIMIT 5;"
    rows_logs = db_manager.execute_read(query_logs)
    if not rows_logs:
        print("  (Chưa có bản ghi nào)")
    else:
        print(f"{'Ticket ID (Rút gọn)':<20} | {'Kênh':<10} | {'Trạng thái':<15} | {'Mức độ':<10} | {'Nội dung tin nhắn'}")
        print("-" * 90)
        for r in rows_logs:
            short_id = r['ticket_id'][:18] + ".." if len(r['ticket_id']) > 18 else r['ticket_id']
            msg = r['message'][:35] + "..." if len(r['message']) > 35 else r['message']
            print(f"{short_id:<20} | {r['channel']:<10} | {r['status']:<15} | {r['severity']:<10} | {msg}")
            
    print("=" * 90 + "\n")

if __name__ == '__main__':
    main()
