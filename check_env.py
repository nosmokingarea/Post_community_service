#!/usr/bin/env python3
"""
환경변수 확인 스크립트
서비스 시작 전에 필요한 환경변수가 설정되었는지 확인합니다.
"""

import os
import sys

def check_environment_variables():
    """환경변수 확인"""
    print("🔍 환경변수 확인 중...")
    
    # 필수 환경변수 목록
    required_vars = {
        'DATABASE_URL': '데이터베이스 연결 URL',
        'AWS_ACCESS_KEY_ID': 'AWS 액세스 키 ID',
        'AWS_SECRET_ACCESS_KEY': 'AWS 시크릿 액세스 키',
        'SECRET_KEY': 'Flask 보안 키'
    }
    
    # 선택적 환경변수 목록 (기본값 있음)
    optional_vars = {
        'S3_BUCKET_NAME': 'S3 버킷 이름 (기본값: karina-winter)',
        'S3_REGION': 'S3 리전 (기본값: ap-northeast-2)',
        'S3_FOLDER_PREFIX': 'S3 폴더 접두사 (기본값: image_files)',
        'MAX_FILE_SIZE': '최대 파일 크기 (기본값: 5242880)',
        'COGNITO_USER_POOL_ID': 'Cognito 사용자 풀 ID (기본값: ap-northeast-2_nneGIIVuJ)',
        'COGNITO_REGION': 'Cognito 리전 (기본값: ap-northeast-2)',
        'COGNITO_CLIENT_ID': 'Cognito 클라이언트 ID (기본값: 2v16jp80j40neuuhtlgg8t)'
    }
    
    print("\n📋 필수 환경변수:")
    missing_required = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # 보안상 민감한 정보는 일부만 표시
            if 'SECRET' in var or 'KEY' in var:
                display_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: 설정되지 않음 - {description}")
            missing_required.append(var)
    
    print("\n📋 선택적 환경변수:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"⚪ {var}: 기본값 사용 - {description}")
    
    print("\n" + "="*50)
    
    if missing_required:
        print("❌ 필수 환경변수가 설정되지 않았습니다!")
        print("\n다음 환경변수를 설정하세요:")
        for var in missing_required:
            print(f"  - {var}")
        print("\n설정 방법:")
        print("Windows PowerShell:")
        print(f"  $env:{missing_required[0]}=\"your-value\"")
        print("\nLinux/Mac:")
        print(f"  export {missing_required[0]}=\"your-value\"")
        return False
    else:
        print("🎉 모든 필수 환경변수가 설정되었습니다!")
        print("\n서비스를 시작할 수 있습니다:")
        print("  python app.py")
        return True

if __name__ == "__main__":
    success = check_environment_variables()
    sys.exit(0 if success else 1)
