"""Authentication and security for Bondlink server"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from jose import JWTError, jwt

from server.core.config import Config


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


def hash_password(password: str) -> str:
    """Hash a password
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_token(length: int = 32) -> str:
    """Generate a secure random token
    
    Args:
        length: Token length in bytes
        
    Returns:
        Hex-encoded token
    """
    return secrets.token_hex(length)


def create_access_token(data: Dict[str, Any], config: Config, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token
    
    Args:
        data: Data to encode in the token
        config: Server configuration
        expires_delta: Token expiration time (optional)
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    # Set expiration
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.web_auth.token_expire_minutes)
    
    to_encode.update({"exp": expire})
    
    # Encode JWT
    encoded_jwt = jwt.encode(
        to_encode,
        config.web_auth.secret_key,
        algorithm=config.web_auth.algorithm
    )
    
    return encoded_jwt


def verify_access_token(token: str, config: Config) -> Dict[str, Any]:
    """Verify and decode a JWT access token
    
    Args:
        token: JWT token
        config: Server configuration
        
    Returns:
        Decoded token data
        
    Raises:
        AuthenticationError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            config.web_auth.secret_key,
            algorithms=[config.web_auth.algorithm]
        )
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {e}")


def authenticate_user(username: str, password: str, config: Config) -> Optional[Dict[str, str]]:
    """Authenticate a user
    
    Args:
        username: Username
        password: Plain text password
        config: Server configuration
        
    Returns:
        User info dict if authenticated, None otherwise
    """
    # Find user
    user = None
    for u in config.web_auth.users:
        if u.username == username:
            user = u
            break
    
    if not user:
        return None
    
    # Verify password
    if not verify_password(password, user.password_hash):
        return None
    
    return {
        "username": user.username,
        "role": user.role
    }


def authenticate_client(token: str, config: Config) -> Optional[str]:
    """Authenticate a client connection
    
    Args:
        token: Client authentication token
        config: Server configuration
        
    Returns:
        Client ID if authenticated, None otherwise
    """
    client_id = config.get_client_id_by_token(token)
    return client_id
