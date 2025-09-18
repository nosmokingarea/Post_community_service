#!/usr/bin/env python3
"""
데이터베이스에 media_files, media_count 컬럼 추가하는 마이그레이션 스크립트
"""

import pymysql
import os
import sys

def get_db_connection():
    """데이터베이스 연결"""
    try:
        # 환경변수에서 DB 정보 가져오기
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', 3306))
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', '')
        db_name = os.getenv('DB_NAME', 'post_db')
        
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"데이터베이스 연결 실패: {e}")
        return None

def add_media_columns():
    """media_files, media_count 컬럼 추가"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # media_files 컬럼 추가
            print("media_files 컬럼 추가 중...")
            cursor.execute("""
                ALTER TABLE posts 
                ADD COLUMN media_files JSON NULL 
                COMMENT '미디어 파일 메타데이터 JSON 저장'
            """)
            
            # media_count 컬럼 추가
            print("media_count 컬럼 추가 중...")
            cursor.execute("""
                ALTER TABLE posts 
                ADD COLUMN media_count INT NOT NULL DEFAULT 0 
                COMMENT '미디어 파일 개수'
            """)
            
            connection.commit()
            print("✅ 컬럼 추가 완료!")
            return True
            
    except Exception as e:
        print(f"❌ 컬럼 추가 실패: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def check_columns():
    """컬럼 존재 여부 확인"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("DESCRIBE posts")
            columns = cursor.fetchall()
            
            column_names = [col['Field'] for col in columns]
            
            print("현재 posts 테이블 컬럼:")
            for col in column_names:
                print(f"  - {col}")
            
            has_media_files = 'media_files' in column_names
            has_media_count = 'media_count' in column_names
            
            print(f"\nmedia_files 컬럼 존재: {'✅' if has_media_files else '❌'}")
            print(f"media_count 컬럼 존재: {'✅' if has_media_count else '❌'}")
            
            return has_media_files and has_media_count
            
    except Exception as e:
        print(f"❌ 컬럼 확인 실패: {e}")
        return False
    finally:
        connection.close()

if __name__ == "__main__":
    print("=== 데이터베이스 마이그레이션: 미디어 컬럼 추가 ===")
    
    # 현재 상태 확인
    print("\n1. 현재 컬럼 상태 확인:")
    if check_columns():
        print("✅ 모든 컬럼이 이미 존재합니다!")
        sys.exit(0)
    
    # 컬럼 추가
    print("\n2. 컬럼 추가 실행:")
    if add_media_columns():
        print("\n3. 추가 후 확인:")
        if check_columns():
            print("🎉 마이그레이션 완료! 이미지 업로드 기능이 활성화됩니다.")
        else:
            print("❌ 마이그레이션 실패")
            sys.exit(1)
    else:
        print("❌ 마이그레이션 실패")
        sys.exit(1)
