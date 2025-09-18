#!/usr/bin/env python3
"""
S3 권한 확인 스크립트
서비스 시작 전에 S3 업로드 권한을 확인합니다.
"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def check_s3_permissions():
    """S3 권한 확인"""
    print("🔍 S3 권한 확인 중...")
    
    # 환경변수 확인
    bucket_name = os.getenv('S3_BUCKET_NAME', 'karina-winter')
    region = os.getenv('S3_REGION', 'ap-northeast-2')
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    print(f"📦 버킷: {bucket_name}")
    print(f"🌍 리전: {region}")
    print(f"📁 폴더: images_files/images/")
    print(f"📏 최대 파일 크기: 5MB")
    print(f"🖼️ 지원 형식: jpg, jpeg, png, gif, webp")
    print(f"🔑 Access Key: {'설정됨' if access_key else '❌ 없음'}")
    print(f"🔐 Secret Key: {'설정됨' if secret_key else '❌ 없음'}")
    
    if not access_key or not secret_key:
        print("❌ AWS 자격증명이 설정되지 않았습니다.")
        print("환경변수를 설정하세요:")
        print("export AWS_ACCESS_KEY_ID=your-access-key")
        print("export AWS_SECRET_ACCESS_KEY=your-secret-key")
        return False
    
    try:
        # S3 클라이언트 생성
        s3_client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # 버킷 존재 확인
        print(f"🔍 버킷 '{bucket_name}' 존재 확인 중...")
        s3_client.head_bucket(Bucket=bucket_name)
        print("✅ 버킷 존재 확인 완료")
        
        # 업로드 권한 확인
        print("📤 업로드 권한 확인 중...")
        test_key = "images_files/test_permission_check.txt"
        test_content = "permission test"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content,
            ContentType='text/plain'
        )
        print("✅ 업로드 권한 확인 완료")
        
        # 테스트 파일 삭제
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print("🗑️ 테스트 파일 삭제 완료")
        
        print("🎉 S3 권한 확인 완료! 모든 권한이 정상입니다.")
        return True
        
    except NoCredentialsError:
        print("❌ AWS 자격증명을 찾을 수 없습니다.")
        return False
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '403':
            print("❌ S3 업로드 권한이 없습니다.")
            print("IAM 정책에서 다음 권한이 필요합니다:")
            print("- s3:PutObject")
            print("- s3:DeleteObject")
            print("- s3:GetObject")
        elif error_code == '404':
            print(f"❌ 버킷 '{bucket_name}'을 찾을 수 없습니다.")
        else:
            print(f"❌ S3 오류: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {str(e)}")
        return False

if __name__ == "__main__":
    success = check_s3_permissions()
    exit(0 if success else 1)
