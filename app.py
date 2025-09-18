"""
Post Service - Flask Application
MSA 아키텍처에서 Post 서비스를 담당하는 Flask 애플리케이션입니다.
"""

import os
import logging
from flask import Flask, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from werkzeug.exceptions import HTTPException, NotFound
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

from post.models import db
from post.routes import bp

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_class=None):
    """Flask 애플리케이션 팩토리"""
    app = Flask(__name__)
    
    # X-Ray 분산 추적 설정 (다른 미들웨어보다 먼저 설정)
    xray_recorder.configure(service='post-service')
    XRayMiddleware(app, xray_recorder)
    
    # 설정 로드
    if config_class:
        app.config.from_object(config_class)
    else:
        # 기본 설정 (config.py의 Config 클래스 사용)
        from config import Config
        app.config.from_object(Config)

    # 이미지 업로드 설정 (개발: 로컬, 운영: S3)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

    # CORS 설정 (OPTIONS 포함, credentials 허용)
    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://www.hhottdogg.shop", "https://hhottdogg.shop"],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    }, supports_credentials=True)

    # 데이터베이스 초기화
    db.init_app(app)
    
    # 데이터베이스 생성
    with app.app_context():
        try:
            from sqlalchemy import create_engine, text
            from urllib.parse import urlparse
            
            db_url = app.config['SQLALCHEMY_DATABASE_URI']
            parsed = urlparse(db_url)
            db_name = parsed.path[1:]
            base_url = f"{parsed.scheme}://{parsed.netloc}/"
            
            engine = create_engine(base_url)
            with engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name}"))
                conn.commit()
            
            logger.info(f"Database '{db_name}' created successfully")
        except Exception as e:
            logger.error(f"Database creation failed: {str(e)}")
    
    # 데이터베이스 테이블 생성
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise

    # Swagger UI 설정
    SWAGGER_URL = '/api/docs'
    API_URL = '/static/swagger.json'
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={
            'app_name': "Post Service API"
        }
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    # 블루프린트 등록
    app.register_blueprint(bp, url_prefix='/api/v1')

    # 전역 에러 핸들러
    @app.errorhandler(HTTPException)
    def handle_exception(e):
        """HTTP 예외 처리"""
        response = {
            "error": {
                "code": e.code,
                "name": e.name,
                "description": e.description
            }
        }
        return jsonify(response), e.code

    @app.errorhandler(NotFound)
    def handle_not_found(e):
        """404 Not Found 예외 처리"""
        response = {
            "error": {
                "code": 404,
                "name": "Not Found",
                "description": "The requested resource was not found"
            }
        }
        return jsonify(response), 404

    @app.errorhandler(Exception)
    def handle_generic_exception(e):
        """일반 예외 처리"""
        logger.error(f"Unhandled exception: {str(e)}")
        response = {
            "error": {
                "code": 500,
                "name": "Internal Server Error",
                "description": "An unexpected error occurred"
            }
        }
        return jsonify(response), 500

    # 업로드된 이미지 파일 서빙 (API용)
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # 테스트용 프론트엔드 페이지 서빙
    @app.route('/', methods=['GET'])
    def index():
        """메인 게시판 페이지"""
        return render_template('index.html')

    @app.route('/write', methods=['GET'])
    def write():
        """게시글 작성 페이지"""
        return render_template('write.html')

    @app.route('/post', methods=['GET'])
    def post_detail():
        """게시글 상세 보기 페이지"""
        return render_template('post_detail.html')

    @app.route('/edit', methods=['GET'])
    def edit_post():
        """게시글 수정 페이지"""
        return render_template('edit_post.html')

    # 헬스체크 엔드포인트
    @app.route('/health', methods=['GET'])
    def health():
        """서비스 상태 확인"""
        return jsonify({
            'status': 'healthy',
            'service': 'Post Service API',
            'version': '1.0.0'
        })

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8082)




