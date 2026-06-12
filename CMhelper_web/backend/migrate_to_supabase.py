import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor

def migrate():
    # 1. Supabase Postgres URL
    supabase_url = os.getenv("DATABASE_URL")
    if not supabase_url:
        print("ERROR: DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        print("Supabase에서 제공하는 Transaction pooling 연결 문자열을 입력하세요.")
        return

    if supabase_url.startswith("postgres://"):
        supabase_url = supabase_url.replace("postgres://", "postgresql://", 1)

    # 2. Local SQLite DB
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sqlite_db_path = os.path.join(base_dir, "data", "cmhelper.db")
    
    if not os.path.exists(sqlite_db_path):
        print("로컬 cmhelper.db 파일을 찾을 수 없습니다. 마이그레이션 할 데이터가 없습니다.")
        return

    print("--- 마이그레이션 시작 ---")
    
    try:
        # Connect to Supabase
        pg_conn = psycopg2.connect(supabase_url)
        pg_cursor = pg_conn.cursor()

        # Connect to SQLite
        sl_conn = sqlite3.connect(sqlite_db_path)
        sl_conn.row_factory = sqlite3.Row
        sl_cursor = sl_conn.cursor()

        # Migrate customers
        sl_cursor.execute("SELECT * FROM customers")
        customers = sl_cursor.fetchall()
        
        if customers:
            print(f"고객 데이터 {len(customers)}건 복사 중...")
            cols = customers[0].keys()
            col_names = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            
            insert_query = f"INSERT INTO customers ({col_names}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
            
            for row in customers:
                pg_cursor.execute(insert_query, tuple(row))
            print("고객 데이터 복사 완료!")

        # Migrate field_definitions
        sl_cursor.execute("SELECT * FROM field_definitions")
        fields = sl_cursor.fetchall()
        
        if fields:
            print(f"입력 필드 설정 데이터 {len(fields)}건 복사 중...")
            cols = fields[0].keys()
            col_names = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            
            insert_query = f"INSERT INTO field_definitions ({col_names}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
            
            for row in fields:
                pg_cursor.execute(insert_query, tuple(row))
            print("입력 필드 설정 데이터 복사 완료!")

        # Migrate consultations
        sl_cursor.execute("SELECT * FROM consultations")
        consults = sl_cursor.fetchall()
        
        if consults:
            print(f"상담 일지 데이터 {len(consults)}건 복사 중...")
            cols = consults[0].keys()
            col_names = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            
            insert_query = f"INSERT INTO consultations ({col_names}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
            
            for row in consults:
                pg_cursor.execute(insert_query, tuple(row))
            print("상담 일지 데이터 복사 완료!")

        pg_conn.commit()
        print("--- 마이그레이션 성공! ---")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        if 'pg_conn' in locals():
            pg_conn.rollback()
    finally:
        if 'pg_cursor' in locals(): pg_cursor.close()
        if 'pg_conn' in locals(): pg_conn.close()
        if 'sl_cursor' in locals(): sl_cursor.close()
        if 'sl_conn' in locals(): sl_conn.close()

if __name__ == "__main__":
    migrate()
