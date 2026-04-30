def create_access_token(user_id: str) -> str:
    return f"access-token-for-{user_id}"


def validate_access_token(token: str) -> bool:
    return token.startswith("access-token")


def issue_jwt_for_user(user_id: str) -> str:
    return f"jwt-token-for-{user_id}"
