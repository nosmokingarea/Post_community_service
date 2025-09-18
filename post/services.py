"""
Post Service Business Logic Layer
비즈니스 로직을 담당하는 서비스 클래스들입니다.
"""

from .models import db, Post, Category, kst_now, PostStatus
from datetime import datetime, timezone, timedelta
import uuid
import requests

class CategoryService:
    """카테고리 관련 비즈니스 로직"""
    
    @staticmethod
    def get_all_categories():
        """모든 카테고리 조회"""
        return Category.query.order_by(Category.name).all()
    
    @staticmethod
    def get_category(category_id):
        """카테고리 조회"""
        return Category.query.get(category_id)
    
    @staticmethod
    def create_category(name):
        """카테고리 생성"""
        category = Category(
            id=str(uuid.uuid4()).replace('-', ''),
            name=name
        )
        
        db.session.add(category)
        db.session.commit()
        return category

class PostService:
    """게시글 관련 비즈니스 로직"""
    
    @staticmethod
    def create_post(title, content, user_id, category_id):
        """게시글 생성"""
        post = Post(
            id=str(uuid.uuid4()).replace('-', ''),
            title=title,
            content=content,
            user_id=user_id,
            category_id=category_id
        )
        
        db.session.add(post)
        db.session.commit()
        return post
    
    @staticmethod
    def get_post(post_id):
        """게시글 조회 (조회수 증가) - visible 상태만 조회 (추가됨)"""
        post = Post.query.filter_by(id=post_id, status=PostStatus.visible).first()
        if post:
            post.view_count += 1
            db.session.commit()
        return post
    
    @staticmethod
    def get_posts_by_category(category_id, page=1, per_page=10):
        """카테고리별 게시글 조회 - visible 상태만 조회 (추가됨)"""
        try:
            return Post.query.filter_by(
                category_id=category_id, status=PostStatus.visible
            ).order_by(Post.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
        except Exception as e:
            # paginate 실패 시 빈 결과 반환
            from flask_sqlalchemy import Pagination
            return Pagination(None, page, per_page, 0, [])
    
    @staticmethod
    def update_post(post_id, **kwargs):
        """게시글 수정"""
        post = Post.query.get(post_id)
        if not post:
            return None
            
        for key, value in kwargs.items():
            if hasattr(post, key):
                setattr(post, key, value)
        
        post.updated_at = kst_now()
        db.session.commit()
        return post
    
    @staticmethod
    def delete_post(post_id):
        """게시글 삭제 (Soft Delete) - status를 'deleted'로 변경 (추가됨)"""
        post = Post.query.get(post_id)
        if not post:
            return False
            
        post.status = PostStatus.deleted
        post.updated_at = kst_now()
        db.session.commit()
        return True



    @staticmethod
    def update_comment_count(post_id):
        """특정 게시글의 댓글 수를 데이터베이스에 업데이트 (추가됨)"""
        try:
            # Comment 서비스에서 댓글 수 가져오기
            response = requests.get(f"http://comment-service:8083/api/v1/posts/{post_id}/comments?page=1&size=1")
            if response.status_code == 200:
                data = response.json()
                comment_count = data.get('data', {}).get('total', 0)
            else:
                comment_count = 0
            
            # Post 테이블의 comment_count 업데이트
            post = Post.query.get(post_id)
            if post:
                post.comment_count = comment_count
                db.session.commit()
                return comment_count
            return 0
        except Exception as e:
            return 0
    
    @staticmethod
    def search_posts(q, page=1, per_page=10):
        """게시글 검색 - visible 상태만 조회 (추가됨)"""
        query = Post.query.filter_by(status=PostStatus.visible)
        
        if q:
            # SQLite에서는 MATCH AGAINST를 지원하지 않으므로 LIKE 검색 사용
            query = query.filter(
                db.or_(
                    Post.title.like(f'%{q}%'),
                    Post.content.like(f'%{q}%')
                )
            )
        
        try:
            return query.order_by(Post.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
        except Exception as e:
            # paginate 실패 시 빈 결과 반환
            from flask_sqlalchemy import Pagination
            return Pagination(None, page, per_page, 0, [])







