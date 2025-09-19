"""
S3 파일 업로드 서비스
karina-winter 버킷의 images_files 폴더에 파일을 저장합니다.
"""

import boto3
import uuid
import os
from datetime import datetime
from flask import current_app
from botocore.exceptions import ClientError, NoCredentialsError
import logging

logger = logging.getLogger(__name__)

class S3Service:
    """S3 파일 업로드 및 관리 서비스"""
    
    def __init__(self):
        """S3 클라이언트 초기화"""
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=current_app.config['S3_REGION'],
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            self.bucket_name = current_app.config['S3_BUCKET_NAME']
            self.folder_prefix = current_app.config['S3_FOLDER_PREFIX']
            
            # S3 권한 확인
            self._check_s3_permissions()
            
            logger.info(f"S3 서비스 초기화 완료 - 버킷: {self.bucket_name}, 폴더: {self.folder_prefix}")
        except Exception as e:
            logger.error(f"S3 서비스 초기화 실패: {str(e)}")
            raise
    
    def _check_s3_permissions(self):
        """S3 업로드 권한 확인"""
        try:
            # 버킷 존재 확인
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            # 테스트 파일로 업로드 권한 확인
            test_key = f"{self.folder_prefix}/test_permission_check.txt"
            test_content = "permission test"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=test_key,
                Body=test_content,
                ContentType='text/plain'
            )
            
            # 테스트 파일 삭제
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=test_key)
            
            logger.info("S3 업로드 권한 확인 완료")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '403':
                raise Exception("S3 업로드 권한이 없습니다. AWS 자격증명을 확인하세요.")
            elif error_code == '404':
                raise Exception(f"S3 버킷 '{self.bucket_name}'을 찾을 수 없습니다.")
            else:
                raise Exception(f"S3 권한 확인 실패: {str(e)}")
        except Exception as e:
            raise Exception(f"S3 연결 실패: {str(e)}")
    
    def generate_s3_key(self, post_id, filename, file_type='image'):
        """S3 객체 키 생성 (이미지만 지원)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_uuid = str(uuid.uuid4())[:8]
        safe_filename = f"{timestamp}_{file_uuid}_{filename}"
        
        # 이미지만 지원하므로 항상 images 폴더 사용
        s3_key = f"{self.folder_prefix}/images/{post_id}/{safe_filename}"
        return s3_key
    
    def upload_file(self, file, post_id, file_type='image'):
        """파일을 S3에 업로드"""
        try:
            # 파일 검증
            if not self._validate_file(file, file_type):
                raise ValueError("파일 검증 실패")
            
            # S3 키 생성
            s3_key = self.generate_s3_key(post_id, file.filename, file_type)
            
            # 파일 업로드
            file.seek(0)  # 파일 포인터를 처음으로 이동
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': file.content_type or 'application/octet-stream'
                }
            )
            
            # API Gateway를 통한 이미지 서빙 URL 생성 (image_files/ 접두사 제거)
            api_gateway_domain = current_app.config.get('API_GATEWAY_DOMAIN', 'api.hhottdogg.shop')
            s3_url = f"https://{api_gateway_domain}/api/v1/images/{s3_key.replace('image_files/', '')}"
            
            logger.info(f"파일 업로드 성공 - S3 Key: {s3_key}")
            
            return {
                's3_key': s3_key,
                's3_url': s3_url,
                'file_name': file.filename,
                'file_size': file.content_length,
                'content_type': file.content_type
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"S3 업로드 실패: {str(e)}")
            
            if error_code == '403':
                raise Exception("S3 업로드 권한이 없습니다. 관리자에게 문의하세요.")
            elif error_code == '404':
                raise Exception(f"S3 버킷 '{self.bucket_name}'을 찾을 수 없습니다.")
            elif error_code == 'NoSuchBucket':
                raise Exception(f"S3 버킷 '{self.bucket_name}'이 존재하지 않습니다.")
            else:
                raise Exception(f"파일 업로드 실패: {str(e)}")
        except Exception as e:
            logger.error(f"파일 업로드 중 오류: {str(e)}")
            raise Exception(f"파일 업로드 중 오류: {str(e)}")
    
    def delete_file(self, s3_key):
        """S3에서 파일 삭제"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"파일 삭제 성공 - S3 Key: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 삭제 실패: {str(e)}")
            return False
    
    def _validate_file(self, file, file_type='image'):
        """파일 검증 (이미지만 지원)"""
        if not file or not file.filename:
            return False
        
        # 파일 크기 검증 (5MB 제한)
        if file.content_length and file.content_length > current_app.config['MAX_FILE_SIZE']:
            logger.warning(f"파일 크기 초과: {file.content_length} bytes (최대: {current_app.config['MAX_FILE_SIZE']} bytes)")
            return False
        
        # 이미지 파일 확장자 검증만
        filename = file.filename.lower()
        allowed_extensions = current_app.config['ALLOWED_IMAGE_EXTENSIONS']
        
        if not any(filename.endswith(f'.{ext}') for ext in allowed_extensions):
            logger.warning(f"허용되지 않은 이미지 확장자: {filename}. 허용된 확장자: {allowed_extensions}")
            return False
        
        return True
    
    def get_file_url(self, s3_key):
        """S3 키로부터 API Gateway URL 생성 (image_files/ 접두사 제거)"""
        api_gateway_domain = current_app.config.get('API_GATEWAY_DOMAIN', 'api.hhottdogg.shop')
        return f"https://{api_gateway_domain}/api/v1/images/{s3_key.replace('image_files/', '')}"
    
    def get_file_content(self, s3_key):
        """S3에서 파일 내용과 메타데이터 조회"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                'body': response['Body'].read(),
                'content_type': response['ContentType'],
                'content_length': response['ContentLength'],
                'last_modified': response['LastModified']
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning(f"파일을 찾을 수 없습니다: {s3_key}")
                return None
            else:
                logger.error(f"파일 조회 실패: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"파일 조회 중 오류: {str(e)}")
            return None

    def list_files(self, post_id, file_type=None):
        """특정 게시물의 파일 목록 조회"""
        try:
            prefix = f"{self.folder_prefix}/"
            if file_type:
                prefix += f"{file_type}s/{post_id}/"
            else:
                prefix += f"*/{post_id}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        's3_key': obj['Key'],
                        's3_url': self.get_file_url(obj['Key']),
                        'file_size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat()
                    })
            
            return files
        except ClientError as e:
            logger.error(f"파일 목록 조회 실패: {str(e)}")
            return []
