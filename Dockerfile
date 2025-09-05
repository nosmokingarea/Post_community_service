# Post Service Docker Image
# MSA 환경에서 Post 서비스를 컨테이너화하기 위한 이미지 (SQLite 버전)

FROM python:3.9-slim

LABEL maintainer="Post Service Team"
LABEL description="Post Service for MSA Architecture (SQLite)"
LABEL version="1.0.0"

WORKDIR /app

# 시스템 패키지 설치 (curl, git 등)
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    iputils-ping \
    dnsutils \
    git \
    nano \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 필요한 디렉토리 생성
RUN mkdir -p uploads && chmod 755 uploads
RUN mkdir -p instance && chmod 755 instance

EXPOSE 5000

# 환경 변수 설정
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Flask 개발 서버 실행
CMD ["python", "app.py"]


