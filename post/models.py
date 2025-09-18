"""
Post Service Database Models
MSA 아키텍처에서 Post 서비스가 관리하는 데이터 구조입니다.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
import enum
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class PostStatus(str, enum.Enum):
    visible = "visible"
    hidden = "hidden"
    deleted = "deleted"

def generate_id():
    """32자리 UUID 생성"""
    return str(uuid.uuid4()).replace('-', '')

def kst_now():
    """한국 시간(KST) 현재 시간 반환"""
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst)



class Category(db.Model):
    """카테고리 정보"""
    __tablename__ = 'categories'
    id = db.Column(db.String(32), primary_key=True, default=generate_id)
    name = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(3), nullable=False, default=kst_now)

class Post(db.Model):
    """게시글 기본 정보 (Cognito user_id로 연결)"""
    __tablename__ = 'posts'
    
    id = db.Column(db.String(32), primary_key=True, default=generate_id)
    No = db.Column(db.Integer, unique=True, autoincrement=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)  # 작성자 이름 (프론트엔드 호환용)
    user_id = db.Column(db.String(36), nullable=True, index=True)  # Cognito user_id 참조 (선택사항)
    category = db.Column(db.String(50), nullable=False, default='일반')  # 카테고리 이름 (프론트엔드 호환용)
    category_id = db.Column(db.String(32), db.ForeignKey('categories.id'), nullable=True, index=True)  # 카테고리 ID (선택사항)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # 게시글 내용
    view_count = db.Column(db.Integer, nullable=False, default=0)
    like_count = db.Column(db.Integer, nullable=False, default=0)
    comment_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.Enum(PostStatus), default=PostStatus.visible)  # ENUM 타입 사용
    
    # 미디어 파일 관련 필드 추가
    media_files = db.Column(db.JSON, nullable=True)  # 파일 메타데이터 JSON 저장
    media_count = db.Column(db.Integer, nullable=False, default=0)  # 파일 개수
    
    created_at = db.Column(db.DateTime(3), nullable=False, default=kst_now)
    updated_at = db.Column(db.DateTime(3), nullable=False, default=kst_now)
    
    # 관계 설정
    category_rel = db.relationship('Category', backref='posts', foreign_keys=[category_id])
    
    def to_dict(self):
        """게시글 정보를 딕셔너리로 변환"""
        return {
            "id": self.id,
            "No": self.No,
            "username": self.username,
            "user_id": self.user_id,
            "category": self.category,
            "category_id": self.category_id,
            "title": self.title,
            "content": self.content,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "status": self.status.value if self.status else None,  # ENUM 값으로 변경 (추가됨)
            "media_files": self.media_files or [],  # 미디어 파일 정보 추가
            "media_count": self.media_count,  # 미디어 파일 개수 추가
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }





class Like(db.Model):
    """게시글 좋아요 기록"""
    __tablename__ = 'likes'

    id = db.Column(db.String(32), primary_key=True, default=generate_id)
    post_id = db.Column(db.String(32), db.ForeignKey('posts.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)  # Cognito 사용자 ID
    created_at = db.Column(db.DateTime(3), nullable=False, default=kst_now)

    # 관계 설정
    post = db.relationship('Post', backref='likes')

    # 복합 유니크 제약조건 (한 사용자가 한 게시글에 좋아요를 한 번만)
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='unique_post_user_like'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat()
        }





