import jwt
import requests
from functools import wraps
from flask import request, jsonify, current_app
from jose import jwt as jose_jwt, JWTError

def get_cognito_public_keys(user_pool_id):
    """Cognito User Pool의 공개키를 가져옵니다."""
    try:
        # Cognito JWKS 엔드포인트
        jwks_url = f"https://cognito-idp.{os.environ.get('COGNITO_REGION')}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        response = requests.get(jwks_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        current_app.logger.error(f"Cognito 공개키 가져오기 실패: {str(e)}")
        return None

def verify_cognito_token(token, user_pool_id):
    """Cognito ID 토큰을 검증합니다."""
    try:
        # 토큰 헤더에서 kid(key ID) 추출
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        if not kid:
            return None, "토큰에 key ID가 없습니다."
        
        # Cognito 공개키 가져오기
        jwks = get_cognito_public_keys(user_pool_id)
        if not jwks:
            return None, "Cognito 공개키를 가져올 수 없습니다."
        
        # 해당 kid의 공개키 찾기
        public_key = None
        for key in jwks['keys']:
            if key['kid'] == kid:
                public_key = key
                break
        
        if not public_key:
            return None, "유효한 공개키를 찾을 수 없습니다."
        
        # JWT 검증
        decoded = jose_jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=os.environ.get('COGNITO_CLIENT_ID'),  # Client ID
            issuer=f'https://cognito-idp.{os.environ.get("COGNITO_REGION")}.amazonaws.com/{user_pool_id}'
        )
        
        return decoded, None
        
    except JWTError as e:
        return None, f"JWT 검증 실패: {str(e)}"
    except Exception as e:
        current_app.logger.error(f"토큰 검증 중 오류: {str(e)}")
        return None, f"토큰 검증 중 오류가 발생했습니다: {str(e)}"

def jwt_required(f):
    """JWT 토큰이 필요한 API 엔드포인트를 위한 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Authorization 헤더에서 토큰 추출
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Authorization 헤더가 없습니다.'}), 401
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Bearer 토큰이 필요합니다.'}), 401
        
        token = auth_header.split(' ')[1]
        if not token:
            return jsonify({'error': '토큰이 없습니다.'}), 401
        
        # Cognito User Pool ID
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        
        # 토큰 검증
        decoded_token, error = verify_cognito_token(token, user_pool_id)
        if error:
            return jsonify({'error': error}), 401
        
        # 요청 컨텍스트에 사용자 정보 저장
        request.user = decoded_token
        
        return f(*args, **kwargs)
    
    return decorated_function

