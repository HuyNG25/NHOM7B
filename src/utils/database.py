import os
import time
import json
import psycopg2
from psycopg2 import pool
from src.utils.logger import app_logger

class DatabaseManager:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "postgres")
        self.port = int(os.getenv("DB_PORT", 5432))
        self.dbname = os.getenv("DB_NAME", "notification_db")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres_password")
        self.pool = None

    def initialize_pool(self):
        """
        Khởi tạo connection pool tới PostgreSQL với cơ chế tự động thử lại (retries).
        """
        retries = 5
        delay = 2
        for i in range(retries):
            try:
                app_logger.info(f"Đang kết nối tới PostgreSQL ({self.host}:{self.port}/{self.dbname}). Lần thử {i + 1}/{retries}...")
                self.pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20,
                    host=self.host,
                    port=self.port,
                    dbname=self.dbname,
                    user=self.user,
                    password=self.password
                )
                app_logger.info("Kết nối Connection Pool PostgreSQL thành công!")
                self.create_tables()
                return
            except psycopg2.OperationalError as e:
                app_logger.warning(f"Chưa thể kết nối tới PostgreSQL: {e}. Thử lại sau {delay} giây...")
                time.sleep(delay)
        
        raise RuntimeError("Không thể kết nối tới PostgreSQL sau nhiều lần thử lại. Ứng dụng dừng khởi chạy.")

    def get_connection(self):
        if not self.pool:
            self.initialize_pool()
        return self.pool.getconn()

    def release_connection(self, conn):
        if self.pool and conn:
            self.pool.putconn(conn)

    def execute_write(self, query: str, params: tuple = None) -> bool:
        """
        Thực thi câu lệnh ghi dữ liệu (INSERT, UPDATE, DELETE).
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            app_logger.error(f"[Database Error - Write Failed]: {e} | Query: {query}")
            return False
        finally:
            if cursor:
                cursor.close()
            self.release_connection(conn)

    def execute_read(self, query: str, params: tuple = None) -> list:
        """
        Thực thi câu lệnh đọc dữ liệu (SELECT) và trả về list dicts (hoặc tuples).
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            # Lấy tên cột để map thành dict
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            app_logger.error(f"[Database Error - Read Failed]: {e} | Query: {query}")
            return []
        finally:
            if cursor:
                cursor.close()
            self.release_connection(conn)

    def create_tables(self):
        """
        Khởi tạo các bảng dữ liệu nếu chưa tồn tại.
        """
        queries = [
            # 1. Bảng lưu log tín hiệu inbound từ B6
            """
            CREATE TABLE IF NOT EXISTS inbound_signals (
                id SERIAL PRIMARY KEY,
                log_type VARCHAR(50) NOT NULL,
                timestamp VARCHAR(100) NOT NULL,
                details JSONB NOT NULL,
                status VARCHAR(50) NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # 2. Bảng lưu lịch sử gửi tin nhắn (notification logs)
            """
            CREATE TABLE IF NOT EXISTS notification_logs (
                ticket_id VARCHAR(100) PRIMARY KEY,
                event_id VARCHAR(100) NOT NULL,
                alert_id VARCHAR(100) NOT NULL,
                channel VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                timestamp VARCHAR(100) NOT NULL,
                severity VARCHAR(50) NOT NULL,
                message TEXT NOT NULL
            );
            """,
            # 3. Bảng cache chống trùng lặp eventId
            """
            CREATE TABLE IF NOT EXISTS event_dedup_cache (
                event_id VARCHAR(255) PRIMARY KEY,
                received_at DOUBLE PRECISION NOT NULL
            );
            """,
            # 4. Bảng cache chống trùng lặp Idempotency-Key
            """
            CREATE TABLE IF NOT EXISTS idempotency_cache (
                idempotency_key VARCHAR(255) PRIMARY KEY,
                response_data JSONB NOT NULL,
                created_at DOUBLE PRECISION NOT NULL
            );
            """
        ]

        for q in queries:
            self.execute_write(q)
        app_logger.info("Khởi tạo cấu trúc các bảng CSDL PostgreSQL thành công (nếu chưa có)!")

# Instance toàn cục sử dụng trong ứng dụng
db_manager = DatabaseManager()
