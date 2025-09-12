"""
Post Service Validation Layer
입력 데이터 검증을 담당하는 검증기 클래스들입니다.
"""

import re
from typing import Dict, List, Optional, Tuple

class PostValidator:
    """게시글 데이터 검증"""
    
    @staticmethod
    def validate_create_post(data: Dict) -> Tuple[bool, List[str]]:
        """게시글 생성 데이터 검증"""
        errors = []
        
        # 제목 검증
        title = data.get('title', '').strip()
        if not title:
            errors.append("제목은 필수입니다")
        elif len(title) > 200:
            errors.append("제목은 200자를 초과할 수 없습니다")
        
        # 작성자 ID 검증
        user_id = data.get('user_id')
        if not user_id:
            errors.append("작성자 ID는 필수입니다")
        elif not PostValidator._is_valid_id(user_id):
            errors.append("올바르지 않은 작성자 ID 형식입니다")
        

        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_update_post(data: Dict) -> Tuple[bool, List[str]]:
        """게시글 수정 데이터 검증"""
        errors = []
        
        # 제목 검증
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                errors.append("제목은 비어있을 수 없습니다")
            elif len(title) > 200:
                errors.append("제목은 200자를 초과할 수 없습니다")
        
        # 작성자 ID 검증
        if 'user_id' in data:
            user_id = data['user_id']
            if not user_id:
                errors.append("작성자 ID는 비어있을 수 없습니다")
            elif not PostValidator._is_valid_id(user_id):
                errors.append("올바르지 않은 작성자 ID 형식입니다")
        

        
        return len(errors) == 0, errors
    
    @staticmethod
    def _is_valid_id(id_str: str) -> bool:
        """ID 형식 검증 (32자리 문자열)"""
        if not isinstance(id_str, str):
            return False
        return len(id_str) == 32 and id_str.isalnum()



class ReactionValidator:
    """반응 데이터 검증"""
    
    @staticmethod
    def validate_reaction(data: Dict) -> Tuple[bool, List[str]]:
        """반응 데이터 검증"""
        errors = []
        
        user_id = data.get('user_id')
        if not user_id:
            errors.append("사용자 ID는 필수입니다")
        elif not PostValidator._is_valid_id(user_id):
            errors.append("올바르지 않은 사용자 ID 형식입니다")
        
        action = data.get('action')
        if not action:
            errors.append("반응 타입은 필수입니다")
        elif action not in ['LIKE', 'DISLIKE']:
            errors.append("올바르지 않은 반응 타입입니다")
        
        return len(errors) == 0, errors

class SearchValidator:
    """검색 데이터 검증"""
    
    @staticmethod
    def validate_search_params(params: Dict) -> Tuple[bool, List[str]]:
        """검색 파라미터 검증"""
        errors = []
        
        # 페이지 번호 검증
        try:
            page = int(params.get('page', 1))
            if page < 1:
                errors.append("페이지 번호는 1 이상이어야 합니다")
        except ValueError:
            errors.append("페이지 번호는 숫자여야 합니다")
        
        # 페이지당 항목 수 검증
        try:
            per_page = int(params.get('per_page', 10))
            if per_page < 1 or per_page > 50:
                errors.append("페이지당 항목 수는 1~50 사이여야 합니다")
        except ValueError:
            errors.append("페이지당 항목 수는 숫자여야 합니다")
        
        # 검색어 검증
        q = params.get('q', '').strip()
        if q and len(q) > 100:
            errors.append("검색어는 100자를 초과할 수 없습니다")
        

        
        return len(errors) == 0, errors
