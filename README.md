# Post Service

AWS Community Service의 게시글 서비스를 담당하는 Flask 애플리케이션입니다.

## 🚀 빠른 시작

### 사전 요구사항
- Python 3.8+
- MySQL 8.0+
- Docker (선택사항)

### 1단계: 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# Flask Configuration
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_URL=mysql+pymysql://postuser:postpass@localhost:3306/postdb

# AWS Cognito Configuration
COGNITO_USER_POOL_ID=your-cognito-user-pool-id
COGNITO_REGION=ap-northeast-2
COGNITO_CLIENT_ID=your-cognito-client-id

# AWS S3 Configuration (Production)
AWS_S3_BUCKET_NAME=post-images
AWS_S3_REGION=ap-northeast-2

# MSA Service URLs
USER_SERVICE_URL=http://localhost:8081
NOTIFICATION_SERVICE_URL=http://localhost:8082

# Environment
ENVIRONMENT=development
```

### 2단계: 의존성 설치

```bash
pip install -r requirements.txt
```

### 3단계: 데이터베이스 설정

```bash
# 데이터베이스 테이블 생성
python -c "from app import create_app; from post.models import db; app = create_app(); app.app_context().push(); db.create_all()"
```

### 4단계: 서비스 실행

```bash
python app.py
```

서비스가 http://localhost:5000 에서 실행됩니다.

## 🐳 Docker로 실행

```bash
# 이미지 빌드
docker build -t post-service .

# 컨테이너 실행
docker run -p 5000:5000 --env-file .env post-service
```

## ☸️ Kubernetes 배포

### 1단계: 환경변수 설정

Kubernetes Secret을 생성하세요:

```bash
kubectl create secret generic post-service-secrets \
  --from-literal=database-url="mysql+pymysql://postuser:postpass@mysql:3306/postdb" \
  --from-literal=cognito-user-pool-id="your-cognito-user-pool-id" \
  --from-literal=cognito-region="ap-northeast-2" \
  --from-literal=cognito-client-id="your-cognito-client-id" \
  --from-literal=aws-s3-bucket-name="post-images" \
  --from-literal=aws-s3-region="ap-northeast-2" \
  --from-literal=secret-key="your-secret-key-here"
```

### 2단계: 배포

```bash
# 이미지 URI 설정
export IMAGE_URI=your-account-id.dkr.ecr.ap-northeast-2.amazonaws.com/post-service:latest

# 템플릿 변환
envsubst < k8s/deployment.tpl.yaml > k8s/deployment.yaml

# 배포
kubectl apply -f k8s/deployment.yaml
```

## 🔧 CI/CD

이 서비스는 AWS CodeBuild와 EKS를 사용하여 자동 배포됩니다.

### CodeBuild 환경변수

- `AWS_ACCOUNT_ID`: AWS 계정 ID
- `AWS_DEFAULT_REGION`: AWS 리전
- `IMAGE_REPO_NAME`: ECR 리포지토리 이름
- `EKS_CLUSTER_NAME`: EKS 클러스터 이름

## 📁 프로젝트 구조

```
Post-master/
├─ app.py                 # Flask 애플리케이션 진입점
├─ config.py              # 설정 관리
├─ requirements.txt       # Python 의존성
├─ Dockerfile            # Docker 이미지 정의
├─ k8s/                  # Kubernetes 매니페스트
│  └─ deployment.tpl.yaml
├─ buildspec.yml         # CodeBuild 스크립트
└─ post/                 # 비즈니스 로직
   ├─ models.py          # 데이터베이스 모델
   ├─ routes.py          # API 라우트
   ├─ services.py        # 비즈니스 서비스
   └─ validators.py      # 입력 검증
```

## 🛠️ API 문서

서비스 실행 후 http://localhost:5000/api/docs 에서 Swagger UI를 확인할 수 있습니다.

## 🔍 헬스 체크

```bash
curl http://localhost:5000/health
```
