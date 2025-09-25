"""
Post Service API Routes
MSA 환경에서 독립적으로 동작하는 Post 서비스 API입니다.
"""

import boto3
import os
from flask import Blueprint, request, jsonify, abort, current_app, Response
from .models import db, Post, Like, Category, kst_now, PostStatus
from .services import PostService, CategoryService
from .validators import PostValidator
from .auth_utils import jwt_required
from .s3_service import S3Service
import uuid
import requests
import json
from werkzeug.utils import secure_filename
from PIL import Image
import io
from datetime import datetime
from functools import wraps
from base64 import urlsafe_b64decode

bp = Blueprint('api', __name__, url_prefix='/api/v1')
# ============================================================================
# 사용자 계정 탈퇴 
# ============================================================================

@bp.route('/users/me/deactivate', methods=['OPTIONS'])
def deactivate_me_options():
    # 프리플라이트 요청에 204 반환
    return ('', 204)

@bp.route('/users/me/deactivate', methods=['POST'])
def deactivate_me():
    """계정 완전 삭제: Cognito AdminDeleteUser + 삭제 검증"""
    try:
        # 1) Authorization 헤더에서 JWT 추출
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return api_error("인증이 필요합니다", 401)

        token = auth.split(' ', 1)[1].strip()

        # 2) JWT payload 디코드 (검증 없이 단순 파싱)
        def _decode_jwt_payload(jwt_token):
            try:
                parts = jwt_token.split('.')
                if len(parts) < 2:
                    return None
                payload_b64 = parts[1]
                padding = '=' * (-len(payload_b64) % 4)
                payload_json = urlsafe_b64decode(payload_b64 + padding).decode('utf-8')
                return json.loads(payload_json)
            except Exception:
                return None

        payload = _decode_jwt_payload(token)
        if not payload:
            return api_error("토큰 파싱에 실패했습니다", 400)

        username = payload.get('cognito:username') or payload.get('username')
        if not username:
            return api_error("토큰에 사용자명이 없습니다", 400)

        if not USER_POOL_ID:
            return api_error("서버 환경변수에 USER_POOL_ID가 없습니다", 500)

        # 3) Cognito 사용자 완전 삭제
        try:
            cognito_client.admin_delete_user(UserPoolId=USER_POOL_ID, Username=username)
            current_app.logger.info(f"User {username} deleted successfully from Cognito")
        except Exception as delete_error:
            current_app.logger.error(f"Failed to delete user {username} from Cognito: {str(delete_error)}")
            return api_error(f"Cognito 사용자 삭제 실패: {str(delete_error)}", 500)
        
        # 삭제 확인 (삭제된 사용자는 조회할 수 없으므로 예외 처리)
        try:
            verify = cognito_client.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
            # 여기 도달하면 삭제가 실패한 것
            current_app.logger.error(f"User {username} still exists after deletion attempt")
            return api_error("사용자 삭제에 실패했습니다", 500)
        except cognito_client.exceptions.UserNotFoundException:
            # 사용자가 삭제되어 조회할 수 없음 - 정상적인 상황
            current_app.logger.info(f"User {username} successfully deleted and verified")
            pass
        except Exception as verify_error:
            current_app.logger.error(f"Error verifying user deletion: {str(verify_error)}")
            return api_error(f"사용자 삭제 확인 중 오류: {str(verify_error)}", 500)

        # 4) 로컬 DB 사용자 비활성화 (있을 경우) - User 모델이 없으므로 주석 처리
        # try:
        #     user = User.query.filter_by(username=username).first()
        #     if user:
        #         user.is_active = False
        #         db.session.commit()
        # except Exception:
        #     db.session.rollback()

        return api_response(data={ 'username': username, 'deleted': True }, message="계정이 완전히 삭제되었습니다")
    except Exception as e:
        current_app.logger.error(f"Error in deactivate_me: {str(e)}")
        return api_error(f"계정 삭제 중 오류: {str(e)}", 500)

# AWS Cognito 설정
cognito_client = boto3.client(
    'cognito-idp',
    region_name=os.environ.get('COGNITO_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')

# ============================================================================
# 유틸리티 함수들
# ============================================================================





def generate_id():
    """32자리 UUID 생성"""
    return str(uuid.uuid4()).replace('-', '')

def get_or_create_category(category_name):
    """카테고리 이름으로 카테고리를 조회하거나 생성"""
    try:
        # 기존 카테고리 조회
        category = Category.query.filter_by(name=category_name).first()
        
        if not category:
            # 카테고리가 없으면 새로 생성
            category = Category(name=category_name)
            db.session.add(category)
            db.session.commit()
            current_app.logger.info(f"새 카테고리 생성: {category_name}")
        
        return category
    except Exception as e:
        current_app.logger.error(f"카테고리 처리 중 오류: {str(e)}")
        db.session.rollback()
        return None

def allowed_file(filename):
    """허용된 이미지 파일 형식 확인"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image_locally(file, post_id):
    """로컬에 이미지 저장"""
    upload_folder = os.path.join(current_app.root_path, 'uploads', str(post_id))
    os.makedirs(upload_folder, exist_ok=True)
    
    filename = secure_filename(file.filename)
    timestamp = str(uuid.uuid4())[:8]
    name, ext = os.path.splitext(filename)
    safe_filename = f"{name}_{timestamp}{ext}"
    
    file_path = os.path.join(upload_folder, safe_filename)
    file.save(file_path)
    
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            mime_type = f"image/{img.format.lower()}"
    except Exception as e:
        width, height = None, None
        mime_type = file.content_type or 'application/octet-stream'
    
    relative_path = f"/uploads/{post_id}/{safe_filename}"
    
    return {
        'file_url': relative_path,
        'mime_type': mime_type,
        'width': width,
        'height': height
    }

# ============================================================================
# API 응답 표준화
# ============================================================================

def api_response(data=None, message="Success", status_code=200, meta=None):
    """표준화된 API 응답 생성"""
    response = {
        "success": status_code < 400,
        "message": message,
        "data": data
    }
    
    if meta:
        response["meta"] = meta
    
    return jsonify(response), status_code

def api_error(message="Error", status_code=400, details=None):
    """표준화된 API 에러 응답 생성"""
    response = {
        "success": False,
        "message": message,
        "error": {
            "code": status_code,
            "details": details
        }
    }
    
    return jsonify(response), status_code

# ============================================================================
# 게시글 API 엔드포인트
# ============================================================================

@bp.route('/posts', methods=['GET'])
def list_posts():
    """
    게시글 목록 조회
    ---
    tags:
      - Posts
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: 페이지 번호
      - name: per_page
        in: query
        type: integer
        default: 10
        maximum: 50
        description: 페이지당 항목 수
      - name: q
        in: query
        type: string
        description: 검색어 (제목, 내용)
      - name: visibility
        in: query
        type: string
        enum: [PUBLIC, PRIVATE, UNLISTED]
        default: PUBLIC
        description: 게시글 공개 설정
      - name: status
        in: query
        type: string
        enum: [PUBLISHED, DRAFT, DELETED]
        default: PUBLISHED
        description: 게시글 상태
    responses:
      200:
        description: 게시글 목록 조회 성공
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            data:
              type: array
              items:
                $ref: '#/definitions/Post'
            meta:
              type: object
              properties:
                page:
                  type: integer
                per_page:
                  type: integer
                total:
                  type: integer
                pages:
                  type: integer
    """
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 10)), 50)
        q = request.args.get('q', '').strip()
        category_id = request.args.get('category_id', None)  # 카테고리 필터
        user_id = request.args.get('user_id', None)  # 사용자별 필터 (추가됨)
        sort = request.args.get('sort', 'latest')  # 정렬 방식 (latest: 최신순, popular: 인기순)

        query = Post.query.filter_by(status=PostStatus.visible)  # visible 상태만 조회 (추가됨)
        if category_id:
            query = query.filter_by(category_id=category_id)
        if user_id:  # 사용자별 필터링 (추가됨)
            query = query.filter_by(user_id=user_id)
        
        if q:
            # SQLite에서는 LIKE 검색 사용
            query = query.filter(
                Post.title.like(f'%{q}%')
            )

        # 정렬 적용
        if sort == 'popular':
            query = query.order_by(Post.like_count.desc(), Post.view_count.desc(), Post.created_at.desc())  # 좋아요 → 조회수 → 생성시간 (추가됨)
        else:  # latest (기본값)
            query = query.order_by(Post.No.desc())  # No 컬럼 기준으로 변경 (추가됨)

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        items = []
        for p in pagination.items:
            # 실시간 댓글 수 조회
            try:
                comment_response = requests.get(f"https://api.hhottdogg.shop/api/v1/posts/{p.id}/comments?page=1&size=1", timeout=2)
                if comment_response.status_code == 200:
                    comment_data = comment_response.json()
                    real_comment_count = comment_data.get('data', {}).get('total', 0)
                else:
                    real_comment_count = p.comment_count  # 실패 시 DB 값 사용
            except Exception:
                real_comment_count = p.comment_count  # 실패 시 DB 값 사용
            
            items.append({
                "id": p.id,
                "title": p.title,
                "content": p.content,
                "username": p.username,
                "user_id": p.user_id,
                "category": p.category,
                "view_count": p.view_count,
                "like_count": p.like_count,
                "comment_count": real_comment_count,  # 실시간 댓글 수 사용
                "media_files": p.media_files or [],  # 미디어 파일 정보 추가
                "media_count": p.media_count,  # 미디어 파일 개수 추가
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat() if p.updated_at else None
            })

        meta = {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages
        }

        return api_response(data=items, meta=meta)
        
    except Exception as e:
        current_app.logger.error(f"Error in list_posts: {str(e)}")
        return api_error("게시글 목록 조회 중 오류가 발생했습니다", 500)

# IP 기반 중복 조회 방지를 위한 간단한 메모리 캐시
_view_cache = {}

def _should_increment_view(post_id, client_ip):
    """클라이언트 IP 기반으로 조회수 증가 여부 결정"""
    cache_key = f"{post_id}_{client_ip}"
    current_time = datetime.utcnow()
    
    # 캐시에서 마지막 조회 시간 확인
    if cache_key in _view_cache:
        last_view_time = _view_cache[cache_key]
        # 2분(120초) 이내 재조회 시 증가 방지
        if (current_time - last_view_time).total_seconds() < 120:
            return False
    
    # 조회 시간 업데이트
    _view_cache[cache_key] = current_time
    return True

@bp.route('/posts/<post_id>', methods=['GET'])
def get_post(post_id):
    """
    게시글 단건 조회
    ---
    tags:
      - Posts
    parameters:
      - name: post_id
        in: path
        type: string
        required: true
        description: 게시글 ID
    responses:
      200:
        description: 게시글 조회 성공
        schema:
          $ref: '#/definitions/Post'
      404:
        description: 게시글을 찾을 수 없음
    """
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        post = Post.query.filter_by(id=post_id, status='visible').first()  # visible 상태만 조회 (추가됨)
        if not post:
            return api_error("게시글을 찾을 수 없습니다", 404)
            
        # 클라이언트 IP 기반 중복 조회 방지
        client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', 'unknown')
        should_increment = _should_increment_view(post_id, client_ip)
        
        if should_increment:
            post.view_count += 1
            db.session.commit()
        
        # 실시간 댓글 수 조회
        try:
            comment_response = requests.get(f"https://api.hhottdogg.shop/api/v1/posts/{post.id}/comments?page=1&size=1", timeout=2)
            if comment_response.status_code == 200:
                comment_data = comment_response.json()
                real_comment_count = comment_data.get('data', {}).get('total', 0)
            else:
                real_comment_count = post.comment_count  # 실패 시 DB 값 사용
        except Exception:
            real_comment_count = post.comment_count  # 실패 시 DB 값 사용
        
        data = {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "username": post.username,
            "user_id": post.user_id,
            "category": post.category,
            "view_count": post.view_count,
            "like_count": post.like_count,
            "comment_count": real_comment_count,  # 실시간 댓글 수 사용
            "media_files": post.media_files or [],  # 미디어 파일 정보 추가
            "media_count": post.media_count,  # 미디어 파일 개수 추가
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat() if post.updated_at else None
        }
        
        return api_response(data=data)
        
    except Exception as e:
        current_app.logger.error(f"Error in get_post: {str(e)}")
        return api_error("게시글 조회 중 오류가 발생했습니다", 500)





@bp.route('/posts', methods=['POST'])
@jwt_required
def create_post():
    """게시글 작성"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': '요청 데이터가 없습니다.'}), 400
        
        # 필수 필드 검증
        required_fields = ['title', 'content', 'category']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} 필드가 필요합니다.'}), 400
        
        # JWT 토큰에서 사용자 정보 추출 (임시로 비활성화된 경우 대비)
        current_user = getattr(request, 'current_user', None)
        if current_user:
            user_sub = current_user.get("sub")
            user_name = current_user.get("cognito:username") or current_user.get("username") or "Anonymous"
        else:
            # JWT 검증이 비활성화된 경우 요청 데이터에서 사용자 정보 추출
            user_sub = data.get('user_id', 'anonymous_user')
            user_name = data.get('username', 'Anonymous')
        
        # user_sub가 없으면 에러
        if not user_sub:
            current_app.logger.error(f"사용자 sub 정보가 없음: {current_user}")
            return jsonify({'error': '사용자 정보를 확인할 수 없습니다.'}), 400
        
        # 카테고리 처리
        category_name = data['category']
        category = get_or_create_category(category_name)
        if not category:
            return jsonify({'error': '카테고리 처리 중 오류가 발생했습니다.'}), 500
        
        # 다음 No 값 계산
        from sqlalchemy import func
        max_no = db.session.query(func.max(Post.No)).scalar()
        next_no = (max_no or 0) + 1
        
        # 게시글 생성
        new_post = Post(
            title=data['title'],
            content=data['content'],
            username=user_name,
            user_id=user_sub,
            category=category_name,
            category_id=category.id,
            No=next_no
        )
        
        db.session.add(new_post)
        db.session.commit()
        
        # 성공 응답
        return jsonify({
            'success': True,
            'message': '게시글이 성공적으로 작성되었습니다.',
            'data': {
                'id': new_post.id,
                'title': new_post.title,
                'content': new_post.content,
                'username': new_post.username,
                'category': new_post.category,
                'created_at': new_post.created_at.isoformat() if new_post.created_at else None
            }
        }), 201
        
    except Exception as e:
        current_app.logger.error(f'게시글 작성 중 오류: {str(e)}')
        db.session.rollback()
        return jsonify({'error': '게시글 작성 중 오류가 발생했습니다.'}), 500

@bp.route('/posts/<post_id>', methods=['PUT', 'PATCH'])
def update_post(post_id):
    """
    게시글 수정
    ---
    tags:
      - Posts
    parameters:
      - name: post_id
        in: path
        type: string
        required: true
        description: 게시글 ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
            content_md:
              type: string
            content_fileurl:
              type: string
            user_id:
              type: string
            visibility:
              type: string
              enum: [PUBLIC, PRIVATE, UNLISTED]
            status:
              type: string
              enum: [PUBLISHED, DRAFT]
    responses:
      200:
        description: 게시글 수정 성공
      404:
        description: 게시글을 찾을 수 없음
    """
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        post = Post.query.filter_by(id=post_id, status='visible').first()  # visible 상태만 조회 (추가됨)
        if not post:
            return api_error("게시글을 찾을 수 없습니다", 404)
        data = request.get_json(force=True, silent=False)

        if request.method == 'PUT':
            title = (data.get('title') or '').strip()
            content = (data.get('content') or '').strip()
            user_id = data.get('user_id')
            
            if not title or not content or not user_id:
                return api_error("제목, 내용, 작성자 ID는 필수입니다", 400)
                
            post.title = title
            post.content = content
            post.user_id = user_id
        else:
            if 'title' in data:
                post.title = (data['title'] or '').strip()
            if 'content' in data:
                post.content = (data['content'] or '').strip()
            if 'user_id' in data:
                post.user_id = data['user_id']

        # 게시글 내용이 수정되었을 때만 updated_at 업데이트 (추가됨)
        post.updated_at = kst_now()
        db.session.commit()
        return api_response(message="게시글이 성공적으로 수정되었습니다")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in update_post: {str(e)}")
        return api_error("게시글 수정 중 오류가 발생했습니다", 500)

@bp.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    """
    게시글 삭제
    ---
    tags:
      - Posts
    parameters:
      - name: post_id
        in: path
        type: string
        required: true
        description: 게시글 ID
    responses:
      200:
        description: 게시글 삭제 성공
      404:
        description: 게시글을 찾을 수 없음
    """
    try:
        post = Post.query.filter_by(id=post_id, status='visible').first()  # visible 상태만 조회 (추가됨)
        if not post:
            return api_error("게시글을 찾을 수 없습니다", 404)
        
        # Soft Delete: status를 'deleted'로 변경 (추가됨)
        post.status = 'deleted'
        post.updated_at = kst_now()
        db.session.commit()
        return api_response(message="게시글이 성공적으로 삭제되었습니다")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in delete_post: {str(e)}")
        return api_error("게시글 삭제 중 오류가 발생했습니다", 500)

# ============================================================================
# 게시글 반응 API
# ============================================================================

@bp.route('/posts/<post_id>/like', methods=['POST'])
def like_post(post_id):
    """
    게시글 좋아요 (한 유저당 한 게시글에 한 번만)
    ---
    tags:
      - Reactions
    parameters:
      - name: post_id
        in: path
        type: string
        required: true
        description: 게시글 ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: string
              description: 사용자 ID
    responses:
      200:
        description: 좋아요 처리 성공
      400:
        description: 잘못된 요청 데이터
      409:
        description: 이미 좋아요를 누른 게시글
    """
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        current_app.logger.info(f"좋아요 요청 - post_id: {post_id}")
        
        post = Post.query.filter_by(id=post_id, status='visible').first()  # visible 상태만 조회 (추가됨)
        if not post:
            current_app.logger.warning(f"게시글을 찾을 수 없습니다: {post_id}")
            return api_error("게시글을 찾을 수 없습니다", 404)
        
        current_app.logger.info(f"게시글 조회 성공: {post.id}")
        
        data = request.get_json(force=True, silent=False)
        current_app.logger.info(f"요청 데이터: {data}")
        
        user_id = data.get('user_id')
        current_app.logger.info(f"추출된 user_id: {user_id}")
        
        if not user_id:
            current_app.logger.warning("사용자 ID가 없습니다")
            return api_error("사용자 ID는 필수입니다", 400)
        
        # 이미 좋아요를 누른 경우
        existing_like = Like.query.filter_by(post_id=post_id, user_id=user_id).first()
        if existing_like:
            # 좋아요 취소
            db.session.delete(existing_like)
            post.like_count = max(0, post.like_count - 1)
            action = "removed"
        else:
            # 새 좋아요 추가
            new_like = Like(post_id=post_id, user_id=user_id)
            db.session.add(new_like)
            post.like_count += 1
            action = "added"
        
        db.session.commit()
        return api_response(data={
            "like_count": post.like_count,
            "is_liked": action == "added",
            "action": action,
            "message": f"좋아요가 {action}되었습니다"
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in like_post: {str(e)}")
        return api_error("좋아요 처리 중 오류가 발생했습니다", 500)

# ============================================================================
# 카테고리 API
# ============================================================================

@bp.route('/categories', methods=['GET'])
def list_categories():
    """
    카테고리 목록 조회
    ---
    tags:
      - Categories
    responses:
      200:
        description: 카테고리 목록 조회 성공
    """
    try:
        categories = Category.query.all()
        items = [{
            "id": c.id,
            "name": c.name,

            "created_at": c.created_at.isoformat()
        } for c in categories]
        
        return api_response(data=items)
        
    except Exception as e:
        current_app.logger.error(f"Error in list_categories: {str(e)}")
        return api_error("카테고리 목록 조회 중 오류가 발생했습니다", 500)

@bp.route('/categories', methods=['POST'])
def create_category():
    """
    새 카테고리 생성
    ---
    tags:
      - Categories
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
              description: 카테고리 이름

    responses:
      201:
        description: 카테고리 생성 성공
      400:
        description: 잘못된 요청 데이터
    """
    try:
        data = request.get_json(force=True, silent=False)
        name = data.get('name', '').strip()
        
        if not name:
            return api_error("카테고리 이름은 필수입니다", 400)
        
        # 중복 카테고리 확인
        existing_category = Category.query.filter_by(name=name).first()
        if existing_category:
            return api_error("이미 존재하는 카테고리입니다", 400)
        
        category = Category(
            name=name
        )
        db.session.add(category)
        db.session.commit()
        
        return api_response(data={
            "id": category.id,
            "name": category.name,

        }, message="카테고리가 생성되었습니다")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in create_category: {str(e)}")
        return api_error("카테고리 생성 중 오류가 발생했습니다", 500)







# ============================================================================
# 이미지 관리 API
# ============================================================================











@bp.route('/posts/<post_id>/like', methods=['POST'])
def toggle_like(post_id):
    """게시글 좋아요 토글 (좋아요 추가/제거)"""
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        # JWT 토큰에서 사용자 ID 추출 (임시로 request body에서 가져옴)
        data = request.get_json()
        current_app.logger.info(f"좋아요 요청 데이터: {data}")
        
        user_id = data.get('user_id')
        current_app.logger.info(f"추출된 user_id: {user_id}")
        
        if not user_id:
            current_app.logger.warning("사용자 ID가 없습니다.")
            return jsonify({
                "success": False,
                "message": "사용자 ID가 필요합니다."
            }), 400

        # 게시글 존재 확인
        post = Post.query.filter_by(id=post_id, status='visible').first()  # visible 상태만 조회 (추가됨)
        current_app.logger.info(f"게시글 조회 결과: {post.id if post else 'None'}")
        
        if not post:
            current_app.logger.warning(f"게시글을 찾을 수 없습니다: {post_id}")
            return jsonify({
                "success": False,
                "message": "게시글을 찾을 수 없습니다."
            }), 404

        # 기존 좋아요 확인
        existing_like = Like.query.filter_by(
            post_id=post_id, 
            user_id=user_id
        ).first()
        
        current_app.logger.info(f"기존 좋아요 상태: {existing_like.id if existing_like else 'None'}")

        if existing_like:
            # 좋아요 취소
            current_app.logger.info("좋아요 취소 처리")
            db.session.delete(existing_like)
            post.like_count = max(0, post.like_count - 1)  # 음수가 되지 않도록
            action = "removed"
        else:
            # 좋아요 추가
            current_app.logger.info("좋아요 추가 처리")
            new_like = Like(
                post_id=post_id,
                user_id=user_id
            )
            db.session.add(new_like)
            post.like_count += 1
            action = "added"

        db.session.commit()
        current_app.logger.info(f"좋아요 처리 완료: {action}, 현재 좋아요 수: {post.like_count}")

        return jsonify({
            "success": True,
            "message": f"좋아요가 {action}되었습니다.",
            "data": {
                "action": action,
                "like_count": post.like_count,
                "is_liked": action == "added"
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"좋아요 토글 중 오류: {str(e)}")
        return jsonify({
            "success": False,
            "message": "좋아요 처리 중 오류가 발생했습니다."
        }), 500

@bp.route('/posts/<post_id>/like/status', methods=['GET'])
def get_like_status(post_id):
    """사용자의 게시글 좋아요 상태 확인"""
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                "success": False,
                "message": "사용자 ID가 필요합니다."
            }), 400

        # 좋아요 상태 확인
        like = Like.query.filter_by(
            post_id=post_id, 
            user_id=user_id
        ).first()

        return jsonify({
            "success": True,
            "data": {
                "is_liked": like is not None
            }
        })

    except Exception as e:
        current_app.logger.error(f"좋아요 상태 확인 중 오류: {str(e)}")
        return jsonify({
            "success": False,
            "message": "좋아요 상태 확인 중 오류가 발생했습니다."
        }), 500



@bp.route('/posts/<post_id>/update-comment-count', methods=['POST'])
def update_post_comment_count(post_id):
    """특정 게시글의 댓글 수를 업데이트 (Comment 서비스에서 호출용) (추가됨)"""
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        # Comment 서비스에서 댓글 수 가져와서 업데이트
        comment_count = PostService.update_comment_count(post_id)
        
        return api_response(data={
            "post_id": post_id,
            "comment_count": comment_count,
            "message": "댓글 수가 업데이트되었습니다"
        })
        
    except Exception as e:
        current_app.logger.error(f"댓글 수 업데이트 실패: {str(e)}")
        return api_error("댓글 수 업데이트에 실패했습니다", 500)

# ============================================================================
# 미디어 파일 업로드 API
# ============================================================================

@bp.route('/posts/media/check-permissions', methods=['GET'])
@jwt_required
def check_s3_permissions():
    """S3 업로드 권한 확인"""
    try:
        s3_service = S3Service()
        return api_response(
            data={
                "has_permission": True,
                "bucket_name": current_app.config['S3_BUCKET_NAME'],
                "folder_prefix": current_app.config['S3_FOLDER_PREFIX'],
                "max_file_size": current_app.config['MAX_FILE_SIZE'],
                "allowed_image_extensions": list(current_app.config['ALLOWED_IMAGE_EXTENSIONS']),
                "file_type_support": "image_only"
            },
            message="S3 업로드 권한이 있습니다"
        )
    except Exception as e:
        current_app.logger.error(f"S3 권한 확인 실패: {str(e)}")
        return api_error(f"S3 업로드 권한이 없습니다: {str(e)}", 403)

@bp.route('/posts/<post_id>/media', methods=['POST'])
@jwt_required
def upload_media(post_id):
    """게시물에 미디어 파일 업로드 (S3에 저장)"""
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        # 게시물 존재 확인
        post = Post.query.filter_by(id=post_id, status=PostStatus.visible).first()
        if not post:
            return api_error("게시물을 찾을 수 없습니다", 404)
        
        # 파일 확인 (단일 파일 또는 다중 파일 지원)
        uploaded_files = []
        
        # 단일 파일 업로드 (기존 방식)
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                uploaded_files.append(file)
        
        # 다중 파일 업로드 (새로운 방식)
        if 'files[]' in request.files:
            files = request.files.getlist('files[]')
            for file in files:
                if file.filename != '':
                    uploaded_files.append(file)
        
        if not uploaded_files:
            return api_error("업로드할 파일이 없습니다", 400)
        
        # 이미지 파일만 지원
        file_type = 'image'  # 항상 이미지로 고정
        
        # S3에 파일들 업로드
        s3_service = S3Service()
        media_infos = []
        
        for file in uploaded_files:
            try:
                upload_result = s3_service.upload_file(file, post_id, file_type)
                
                # 미디어 파일 메타데이터 생성
                media_info = {
                    "id": str(uuid.uuid4()),
                    "file_name": upload_result['file_name'],
                    "s3_key": upload_result['s3_key'],
                    "s3_url": upload_result['s3_url'],
                    "file_type": file_type,
                    "file_size": upload_result['file_size'],
                    "content_type": upload_result['content_type'],
                    "uploaded_at": kst_now().isoformat()
                }
                
                media_infos.append(media_info)
                
            except Exception as e:
                current_app.logger.error(f"파일 업로드 실패: {file.filename}, {str(e)}")
                continue  # 실패한 파일은 건너뛰고 계속 진행
        
        if not media_infos:
            return api_error("모든 파일 업로드에 실패했습니다", 500)
        
        # 게시물의 미디어 파일 목록에 추가
        if not post.media_files:
            post.media_files = []
        
        post.media_files.extend(media_infos)
        post.media_count = len(post.media_files)
        post.updated_at = kst_now()
        
        db.session.commit()
        
        # 응답 데이터 결정
        if len(media_infos) == 1:
            # 단일 파일 업로드인 경우
            return api_response(data=media_infos[0], message="파일이 성공적으로 업로드되었습니다")
        else:
            # 다중 파일 업로드인 경우
            return api_response(data={
                "uploaded_files": media_infos,
                "total_count": len(media_infos),
                "failed_count": len(uploaded_files) - len(media_infos)
            }, message=f"{len(media_infos)}개 파일이 성공적으로 업로드되었습니다")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"미디어 파일 업로드 실패: {str(e)}")
        return api_error("파일 업로드 중 오류가 발생했습니다", 500)

@bp.route('/posts/<post_id>/media/<media_id>', methods=['DELETE'])
@jwt_required
def delete_media(post_id, media_id):
    """게시물에서 미디어 파일 삭제 (S3에서도 삭제)"""
    try:
        # post_id 유효성 검사
        if not post_id or post_id == 'null' or post_id == 'undefined':
            return api_error("유효하지 않은 게시물 ID입니다", 400)
        
        # 게시물 존재 확인
        post = Post.query.filter_by(id=post_id, status=PostStatus.visible).first()
        if not post:
            return api_error("게시물을 찾을 수 없습니다", 404)
        
        # 미디어 파일 찾기
        if not post.media_files:
            return api_error("미디어 파일이 없습니다", 404)
        
        media_to_delete = None
        for media in post.media_files:
            if media['id'] == media_id:
                media_to_delete = media
                break
        
        if not media_to_delete:
            return api_error("미디어 파일을 찾을 수 없습니다", 404)
        
        # S3에서 파일 삭제
        s3_service = S3Service()
        s3_service.delete_file(media_to_delete['s3_key'])
        
        # 게시물에서 미디어 파일 제거
        post.media_files = [m for m in post.media_files if m['id'] != media_id]
        post.media_count = len(post.media_files)
        post.updated_at = kst_now()
        
        db.session.commit()
        
        return api_response(message="미디어 파일이 성공적으로 삭제되었습니다")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"미디어 파일 삭제 실패: {str(e)}")
        return api_error("파일 삭제 중 오류가 발생했습니다", 500)

@bp.route('/images/<path:image_path>', methods=['GET'])
def serve_image(image_path):
    """S3에서 이미지 파일을 프록시하여 서빙 (API Gateway를 통한 접근)"""
    try:
        # S3 키 생성 (image_files/ 접두사 추가)
        s3_key = f"image_files/{image_path}"
        
        # S3에서 파일 조회
        s3_service = S3Service()
        file_data = s3_service.get_file_content(s3_key)
        
        if not file_data:
            return api_error("이미지를 찾을 수 없습니다", 404)
        
        # 파일 내용과 메타데이터 반환
        return Response(
            file_data['body'],
            mimetype=file_data['content_type'],
            headers={
                'Cache-Control': 'public, max-age=31536000',  # 1년 캐시
                'Content-Length': str(file_data['content_length']),
                'Last-Modified': file_data['last_modified'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"이미지 서빙 실패: {str(e)}")
        return api_error("이미지 서빙 중 오류가 발생했습니다", 500)




