from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedReviewer(BaseModel):
    email: str
    subject: str = "placeholder-reviewer"
    display_name: str = "Reviewer"


def extract_bearer_token(authorization_header: str | None) -> str:
    if authorization_header is None:
        raise ValueError("Missing Authorization header.")
    scheme, _, token = authorization_header.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise ValueError("Authorization header must use the Bearer scheme.")
    return token.strip()


def validate_entra_token(authorization_header: str | None) -> AuthenticatedReviewer:
    token = extract_bearer_token(authorization_header)
    if "@" in token:
        return AuthenticatedReviewer(email=token, subject=token, display_name=token.split("@", maxsplit=1)[0])
    return AuthenticatedReviewer(email="reviewer@verdecora.example.com", subject=token, display_name="Reviewer")
