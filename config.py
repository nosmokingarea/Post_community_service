"""
Post Service Configuration
MSA 환경에서 Post 서비스의 설정을 관리합니다.
"""

import os

class Config:
    # 보안 키 (운영 환경에서는 반드시 환경 변수로 설정)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 세션 설정 - 탭 종료 시 자동 로그아웃을 위해 False로 설정
    SESSION_PERMANENT = False
    SESSION_COOKIE_SECURE = False  # 개발 환경에서는 False, 운영 환경에서는 True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # 데이터베이스 설정 - Docker 환경에서는 mysql 서비스명 사용
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # AWS Cognito 설정
    COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', 'ap-northeast-2_nneGIIVuJ')
    COGNITO_REGION = os.environ.get('COGNITO_REGION', 'ap-northeast-2')
    COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID', '2v16jp80j40neuuhtlgg8t')
    
    # S3 설정
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'karina-winter')
    S3_REGION = os.environ.get('S3_REGION', 'ap-northeast-2')
    S3_FOLDER_PREFIX = os.environ.get('S3_FOLDER_PREFIX', 'image_files')
    
    # 파일 업로드 설정 (이미지만 지원)
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 5 * 1024 * 1024))  # 5MB
    ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    # ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'avi', 'mov'}  # 비디오 지원 비활성화
    
    # AWS X-Ray 설정
    AWS_XRAY_TRACING_NAME = os.environ.get('AWS_XRAY_TRACING_NAME', 'post-service')
    AWS_XRAY_CONTEXT_MISSING = os.environ.get('AWS_XRAY_CONTEXT_MISSING', 'LOG_ERROR')


