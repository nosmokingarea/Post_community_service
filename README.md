# Post Service - MSA 게시판 서비스

AWS 기반 마이크로서비스 아키텍처에서 게시판 기능을 담당하는 독립적인 Flask 서비스입니다.

## 🏗️ 시스템 아키텍처

### 전체 시스템 흐름도
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   CloudFront    │
│   (React)       │◄──►│   (AWS)         │◄──►│   (CDN)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │     Load Balancer       │
                    │   (AWS NLB/ALB)         │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │      EKS Cluster        │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │   Post Service   │   │
                    │  │   (Flask)        │   │
                    │  └─────────────────┘   │
                    │           │             │
                    │           ▼             │
                    │  ┌─────────────────┐   │
                    │  │   RDS MySQL     │   │
                    │  │   (Multi-AZ)    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
```

### 서비스 구성 요소

#### 1. **Frontend Layer**
- **React 애플리케이션**: 사용자 인터페이스
- **도메인**: `https://hhottdogg.shop`
- **CORS 설정**: Post Service와 직접 통신

#### 2. **API Gateway Layer**
- **AWS API Gateway**: HTTP API 엔드포인트 관리
- **Cognito Authorizer**: JWT 토큰 기반 인증
- **Rate Limiting**: API 호출 제한

#### 3. **Load Balancing**
- **AWS NLB**: Layer 4 로드 밸런싱
- **Health Check**: `/health` 엔드포인트 모니터링
- **Cross-Zone**: 다중 AZ 트래픽 분산

#### 4. **Container Orchestration**
- **EKS Cluster**: Kubernetes 기반 컨테이너 관리
- **Namespace**: `post-service`
- **HPA**: CPU 기반 자동 스케일링 (1-3 replicas)
- **Resource Limits**: CPU 700m, Memory 1Gi

#### 5. **Data Layer**
- **RDS MySQL**: Multi-AZ 고가용성 데이터베이스
- **자동 DB 생성**: 애플리케이션 시작 시 `postdb` 자동 생성
- **Connection Pooling**: 효율적인 DB 연결 관리

#### 6. **CI/CD Pipeline**
- **GitHub**: 소스 코드 저장소
- **CodeBuild**: Docker 이미지 빌드
- **ECR**: 컨테이너 이미지 저장소
- **CodePipeline**: 자동 배포 파이프라인

## 🚀 핵심 기능

### 1. **게시글 관리**
- **CRUD 작업**: 생성, 조회, 수정, 삭제
- **Soft Delete**: 논리적 삭제 (status='deleted')
- **자동 번호**: 게시글 번호 자동 할당
- **조회수 관리**: IP 기반 중복 조회 방지

### 2. **카테고리 시스템**
- **동적 생성**: 게시글 작성 시 자동 카테고리 생성
- **관계형 연결**: Post-Category 외래키 관계
- **유니크 제약**: 카테고리명 중복 방지

### 3. **좋아요 시스템**
- **토글 기능**: 좋아요 추가/취소
- **중복 방지**: 사용자당 게시글당 1회 제한
- **실시간 카운트**: 좋아요 수 자동 업데이트

### 4. **검색 및 필터링**
- **제목 검색**: LIKE 기반 부분 일치 검색
- **카테고리 필터**: 카테고리별 게시글 조회
- **사용자 필터**: 작성자별 게시글 조회
- **정렬 옵션**: 최신순, 인기순

### 5. **인증 및 보안**
- **AWS Cognito**: JWT 토큰 기반 인증
- **토큰 검증**: RS256 알고리즘 서명 검증
- **사용자 관리**: 계정 비활성화 기능

## 📊 데이터 모델

### Post 테이블
```sql
CREATE TABLE posts (
    id VARCHAR(32) PRIMARY KEY,           -- UUID 기반 고유 ID
    No INT UNIQUE AUTO_INCREMENT,         -- 게시글 번호
    username VARCHAR(100) NOT NULL,        -- 작성자명
    user_id VARCHAR(36),                  -- Cognito 사용자 ID
    category VARCHAR(50) DEFAULT '일반',    -- 카테고리명
    category_id VARCHAR(32),              -- 카테고리 ID (FK)
    title VARCHAR(200) NOT NULL,          -- 제목
    content TEXT NOT NULL,                -- 내용
    view_count INT DEFAULT 0,             -- 조회수
    like_count INT DEFAULT 0,             -- 좋아요 수
    comment_count INT DEFAULT 0,          -- 댓글 수
    status ENUM('visible','hidden','deleted') DEFAULT 'visible',
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Category 테이블
```sql
CREATE TABLE categories (
    id VARCHAR(32) PRIMARY KEY,           -- UUID 기반 고유 ID
    name VARCHAR(50) UNIQUE NOT NULL,     -- 카테고리명
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP
);
```

### Like 테이블
```sql
CREATE TABLE likes (
    id VARCHAR(32) PRIMARY KEY,           -- UUID 기반 고유 ID
    post_id VARCHAR(32) NOT NULL,          -- 게시글 ID (FK)
    user_id VARCHAR(36) NOT NULL,          -- 사용자 ID
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_post_user_like (post_id, user_id)
);
```

## 🔧 기술 스택

### Backend
- **Framework**: Flask 2.3.3
- **Database**: MySQL 8.0+ (PyMySQL 1.1.0)
- **ORM**: SQLAlchemy 3.0.5
- **Authentication**: AWS Cognito + JWT
- **Image Processing**: Pillow 10.0.1

### Infrastructure
- **Container**: Docker
- **Orchestration**: Kubernetes (EKS)
- **Load Balancer**: AWS NLB
- **Database**: RDS MySQL Multi-AZ
- **Storage**: ECR (Container Registry)

### CI/CD
- **Source Control**: GitHub
- **Build**: AWS CodeBuild
- **Deploy**: AWS CodePipeline
- **Registry**: Amazon ECR

## 🚀 빠른 시작

### 사전 요구사항
- Python 3.9+
- MySQL 8.0+
- Docker (선택사항)
- AWS CLI (배포용)

### 1단계: 환경변수 설정

`.env` 파일 생성:
```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/postdb

# AWS Cognito Configuration
COGNITO_USER_POOL_ID=ap-northeast-2_nneGIIVuJ
COGNITO_REGION=ap-northeast-2
COGNITO_CLIENT_ID=2v16jp80j40neuuhtlgg8t

# AWS Credentials (운영환경)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### 2단계: 의존성 설치

```bash
pip install -r requirements.txt
```

### 3단계: 서비스 실행

```bash
# 로컬 실행
python app.py

# 또는 Docker 실행
docker build -t post-service .
docker run -p 8082:8082 --env-file .env post-service
```

서비스가 `http://localhost:8082`에서 실행됩니다.

## 📡 API 엔드포인트

### 게시글 API
```bash
# 게시글 목록 조회
GET /api/v1/posts?page=1&per_page=10&q=검색어&category_id=카테고리ID

# 게시글 상세 조회
GET /api/v1/posts/{post_id}

# 게시글 작성 (인증 필요)
POST /api/v1/posts
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
{
  "title": "제목",
  "content": "내용",
  "category": "카테고리명"
}

# 게시글 수정
PUT /api/v1/posts/{post_id}
PATCH /api/v1/posts/{post_id}

# 게시글 삭제 (Soft Delete)
DELETE /api/v1/posts/{post_id}
```

### 좋아요 API
```bash
# 좋아요 토글
POST /api/v1/posts/{post_id}/like
Content-Type: application/json
{
  "user_id": "사용자ID"
}

# 좋아요 상태 확인
GET /api/v1/posts/{post_id}/like/status?user_id=사용자ID
```

### 카테고리 API
```bash
# 카테고리 목록
GET /api/v1/categories

# 카테고리 생성
POST /api/v1/categories
Content-Type: application/json
{
  "name": "카테고리명"
}
```

### 시스템 API
```bash
# 헬스체크
GET /health

# API 문서
GET /api/docs
```

## ☸️ Kubernetes 배포

### 1단계: 시크릿 생성

```bash
# 데이터베이스 시크릿
kubectl create secret generic post-db-secret \
  --from-literal=database-url="mysql+pymysql://user:pass@rds-endpoint:3306/postdb" \
  -n post-service

# 애플리케이션 시크릿
kubectl create secret generic post-secrets \
  --from-literal=cognito-user-pool-id="ap-northeast-2_nneGIIVuJ" \
  --from-literal=cognito-region="ap-northeast-2" \
  --from-literal=cognito-client-id="2v16jp80j40neuuhtlgg8t" \
  --from-literal=secret-key="your-secret-key" \
  -n post-service
```

### 2단계: 배포

```bash
# 네임스페이스 생성
kubectl create namespace post-service

# 배포 실행
kubectl apply -f k8s/deployment.yaml

# 상태 확인
kubectl get pods -n post-service
kubectl get svc -n post-service
kubectl get hpa -n post-service
```

### 3단계: 로드밸런서 확인

```bash
# NLB 엔드포인트 확인
kubectl get svc post-service -n post-service

# 헬스체크
curl http://<NLB-ENDPOINT>/health
```

## 🔄 CI/CD 파이프라인

### GitHub → CodeBuild → ECR → EKS

1. **소스 코드 푸시**: GitHub main 브랜치
2. **자동 빌드**: CodeBuild가 Docker 이미지 빌드
3. **이미지 푸시**: ECR에 이미지 업로드
4. **자동 배포**: EKS 클러스터에 배포

### 빌드 설정 (buildspec.yml)
```yaml
version: 0.2
phases:
  pre_build:
    commands:
      - aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin $ECR_REPO_URI
  build:
    commands:
      - docker build -t $IMAGE_URI -t $IMAGE_URI_LATEST .
  post_build:
    commands:
      - docker push $IMAGE_URI
      - docker push $IMAGE_URI_LATEST
```

## 🔍 모니터링 및 로깅

### 헬스체크
- **엔드포인트**: `/health`
- **응답**: 서비스 상태, 버전 정보
- **NLB Health Check**: 자동 트래픽 라우팅

### 로깅
- **애플리케이션 로그**: Flask 기본 로거
- **에러 핸들링**: 전역 예외 처리
- **요청 추적**: 상세한 요청/응답 로깅

### 메트릭
- **HPA 메트릭**: CPU 사용률 기반 스케일링
- **리소스 모니터링**: 메모리, CPU 사용량
- **데이터베이스**: 연결 상태, 쿼리 성능

## 🛡️ 보안 고려사항

### 인증 및 인가
- **JWT 토큰**: AWS Cognito 기반 토큰 검증
- **토큰 만료**: 자동 토큰 갱신
- **권한 관리**: 사용자별 접근 제어

### 데이터 보호
- **SQL Injection 방지**: SQLAlchemy ORM 사용
- **XSS 방지**: 입력 데이터 검증 및 이스케이프
- **CSRF 보호**: SameSite 쿠키 설정

### 네트워크 보안
- **HTTPS**: TLS 1.2+ 암호화
- **CORS**: 허용된 도메인만 접근
- **Rate Limiting**: API 호출 제한

## 📁 프로젝트 구조

```
Post_community_service/
├── app.py                    # Flask 애플리케이션 진입점
├── config.py                 # 설정 관리
├── requirements.txt          # Python 의존성
├── Dockerfile               # Docker 이미지 정의
├── buildspec.yml            # CodeBuild 스크립트
├── post-cicd.tf             # Terraform CI/CD 인프라
├── cloudfront-config.json   # CloudFront 설정
├── k8s/                     # Kubernetes 매니페스트
│   └── deployment.yaml      # 배포 설정
└── post/                    # 비즈니스 로직
    ├── models.py            # 데이터베이스 모델
    ├── routes.py            # API 라우트
    ├── services.py          # 비즈니스 서비스
    ├── auth_utils.py        # JWT 인증 유틸리티
    ├── validators.py        # 입력 검증
    └── utils.py             # 공통 유틸리티
```

## 🔧 개발 가이드

### 코드 스타일
- **PEP 8**: Python 코딩 표준 준수
- **Type Hints**: 타입 힌트 사용
- **Docstrings**: 함수/클래스 문서화

### 테스트
```bash
# 단위 테스트 실행
pytest tests/

# 커버리지 확인
pytest --cov=post tests/
```

### 데이터베이스 마이그레이션
```bash
# 마이그레이션 생성
flask db migrate -m "설명"

# 마이그레이션 적용
flask db upgrade
```

## 🚨 트러블슈팅

### 일반적인 문제

#### 1. 데이터베이스 연결 실패
```bash
# 연결 문자열 확인
echo $DATABASE_URL

# 데이터베이스 생성 확인
mysql -h host -u user -p -e "SHOW DATABASES;"
```

#### 2. JWT 토큰 검증 실패
```bash
# Cognito 설정 확인
aws cognito-idp describe-user-pool --user-pool-id $COGNITO_USER_POOL_ID

# 토큰 디코딩 테스트
python -c "import jwt; print(jwt.decode(token, options={'verify_signature': False}))"
```

#### 3. 컨테이너 시작 실패
```bash
# 로그 확인
kubectl logs -f deployment/post-service-deployment -n post-service

# 이벤트 확인
kubectl get events -n post-service --sort-by='.lastTimestamp'
```

### 성능 최적화

#### 1. 데이터베이스 쿼리 최적화
- **인덱스**: user_id, category_id, status 컬럼
- **페이지네이션**: 대용량 데이터 처리
- **연결 풀링**: RDS Proxy 사용 고려

#### 2. 캐싱 전략
- **조회수 캐싱**: Redis/Memcached 도입
- **카테고리 캐싱**: 자주 조회되는 데이터 캐싱
- **CDN**: 정적 자원 캐싱

## 📈 확장성 고려사항

### 수평 확장
- **HPA**: CPU 기반 자동 스케일링
- **데이터베이스**: Read Replica 구성
- **캐싱**: Redis 클러스터

### 수직 확장
- **리소스 증가**: CPU/Memory 할당량 증가
- **데이터베이스**: 인스턴스 크기 업그레이드

## 📞 지원 및 문의

- **이슈 리포트**: GitHub Issues
- **문서**: `/api/docs` (Swagger UI)
- **헬스체크**: `/health`

---

**버전**: 1.0.0  
**최종 업데이트**: 2024년 12월