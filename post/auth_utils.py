"""
Post Service JWT 토큰 처리 유틸리티
Comment 서비스와 동일한 패턴으로 JWT 토큰을 검증하고 사용자 정보를 추출합니다.
"""

import jwt
import requests
import logging
from functools import wraps
from flask import request, current_app
from config import Config

logger = logging.getLogger(__name__)

# Cognito 설정
COGNITO_USER_POOL_ID = Config.COGNITO_USER_POOL_ID
COGNITO_REGION = Config.COGNITO_REGION
COGNITO_CLIENT_ID = Config.COGNITO_CLIENT_ID

def get_cognito_public_keys():
    """Cognito 공개키 가져오기"""
    try:
        url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Cognito 공개키 가져오기 실패: {e}")
        return None

def get_public_keys_from_issuer(issuer: str) -> dict:
    """issuer 기반 공개키 가져오기"""
    try:
        url = f"{issuer}/.well-known/jwks.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"issuer 기반 공개키 가져오기 실패: {e}")
        return None

def verify_cognito_token(token: str) -> dict:
    """
    Cognito JWT 토큰 검증
    - idToken: aud 검증(클라이언트 ID), token_use == "id"
    - accessToken: aud 미검증, issuer 검증, token_use == "access" 및 client_id == 클라이언트 ID
    """
    logger.info(f"JWT 토큰 검증 시작")
    
    # 토큰 형식 검증
    if not token or len(token.split('.')) != 3:
        logger.error("잘못된 JWT 토큰 형식")
        raise Exception("Invalid JWT token format")
    
    try:
        # 토큰 헤더에서 kid 추출
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        if not kid:
            logger.error("kid가 토큰 헤더에 없음")
            raise Exception("Invalid token header")
        
        # Cognito 공개키 가져오기
        public_keys = get_cognito_public_keys()
        
        if not public_keys:
            logger.error("공개키를 가져올 수 없음")
            raise Exception("Failed to get public keys")
        
        # 해당 kid의 공개키 찾기
        public_key = None
        selected_issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
        for i, key in enumerate(public_keys['keys']):
            if key['kid'] == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
        
        if not public_key:
            logger.warning(f"kid {kid}에 해당하는 공개키를 찾을 수 없음")
            raise Exception("Public key not found")
        
        # 토큰 페이로드에서 token_use 확인
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        token_use = unverified_payload.get('token_use')
        
        if not token_use:
            logger.error("token_use가 토큰에 없음")
            raise Exception("token_use not found in token")
        
        logger.info(f"토큰 타입: {token_use}")
        
        issuer = selected_issuer

        # 토큰 검증
        if token_use == 'id':
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=COGNITO_CLIENT_ID,
                issuer=issuer
            )
            if payload.get('token_use') != 'id':
                raise Exception("Invalid token_use for id token")
        elif token_use == 'access':
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                issuer=issuer,
                options={"verify_aud": False}
            )
            if payload.get('token_use') != 'access':
                raise Exception("Invalid token_use for access token")
            if payload.get('client_id') != COGNITO_CLIENT_ID:
                logger.error(f"client_id 불일치: expected={COGNITO_CLIENT_ID}, actual={payload.get('client_id')}")
                raise Exception("Invalid client_id")
        else:
            logger.error(f"알 수 없는 token_use: {token_use}")
            raise Exception("Unknown token_use")

        logger.info("JWT 토큰 검증 완료")
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.error("토큰 만료됨")
        raise Exception("Token expired")
    except jwt.InvalidAudienceError:
        logger.error("잘못된 audience")
        raise Exception("Invalid audience")
    except jwt.InvalidIssuerError:
        logger.error("잘못된 issuer")
        raise Exception("Invalid issuer")
    except jwt.InvalidSignatureError:
        logger.error("서명 검증 실패")
        raise Exception("Invalid signature")
    except jwt.InvalidTokenError as e:
        logger.error(f"잘못된 토큰: {str(e)}")
        raise Exception(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"토큰 검증 실패: {e}")
        raise Exception("Token verification failed")

def jwt_required(f):
    """JWT 토큰 검증 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token or not token.startswith('Bearer '):
            logger.warning("Authorization header missing or invalid format")
            return {"error": "Authorization token required"}, 401
        
        token = token.split(' ')[1]
        
        try:
            # Cognito JWT 토큰 검증
            payload = verify_cognito_token(token)
            request.current_user = payload
            logger.info(f"JWT validation successful for user: {payload.get('sub', 'unknown')}")
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"JWT validation failed: {str(e)}")
            # 더 구체적인 에러 메시지 제공
            if "Token expired" in str(e):
                return {"error": "Token expired"}, 401
            elif "Invalid audience" in str(e):
                return {"error": "Invalid token audience"}, 401
            elif "Invalid issuer" in str(e):
                return {"error": "Invalid token issuer"}, 401
            elif "Invalid token" in str(e):
                return {"error": "Invalid token format"}, 401
            else:
                return {"error": "Token verification failed"}, 401
    
    return decorated_function
