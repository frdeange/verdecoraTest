from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UploadWebSettings(BaseSettings):
    """Runtime settings for the Upload Web application."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    blob_account: str = Field(
        default="https://storage.example.com",
        validation_alias=AliasChoices("BLOB_ACCOUNT", "STORAGE_ACCOUNT_URL"),
    )
    cosmos_url: str = Field(
        default="https://localhost:8081",
        validation_alias=AliasChoices("COSMOS_URL", "COSMOS_ENDPOINT"),
    )
    app_insights_connection_string: str = Field(
        default="",
        validation_alias=AliasChoices("APP_INSIGHTS_CONNECTION_STRING", "APPLICATIONINSIGHTS_CONNECTION_STRING"),
    )
    raw_blob_container: str = Field(default="albaranes-raw", validation_alias=AliasChoices("RAW_BLOB_CONTAINER"))
    upload_sessions_container: str = Field(
        default="upload-sessions",
        validation_alias=AliasChoices("UPLOAD_SESSIONS_CONTAINER"),
    )
    azure_tenant_id: str = Field(default="", validation_alias=AliasChoices("AZURE_TENANT_ID"))
    key_vault_url: str = Field(default="", validation_alias=AliasChoices("KEY_VAULT_URL"))
    docintell_endpoint: str = Field(default="", validation_alias=AliasChoices("DOCINTELL_ENDPOINT"))
    servicebus_namespace: str = Field(
        default="",
        validation_alias=AliasChoices("SERVICEBUS_FQ_NAMESPACE", "SERVICEBUS_NAMESPACE"),
    )
    servicebus_topic: str = Field(
        default="albaran-processing",
        validation_alias=AliasChoices("SERVICEBUS_TOPIC"),
    )
    cosmos_database: str = Field(
        default="verdecora",
        validation_alias=AliasChoices("COSMOS_DATABASE"),
    )
    session_signing_key: str = Field(
        default="dev-only-upload-web-session-signing-key-change-me",
        validation_alias=AliasChoices("SESSION_SIGNING_KEY"),
    )
    allowed_uploader_group: str = Field(
        default="verdecora-store-uploaders",
        validation_alias=AliasChoices("UPLOAD_ALLOWED_GROUP"),
    )


@lru_cache(maxsize=1)
def get_settings() -> UploadWebSettings:
    return UploadWebSettings()
