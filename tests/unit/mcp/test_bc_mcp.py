from __future__ import annotations

from types import SimpleNamespace

from mcp.types import CallToolResult, TextContent

from src.mcp.bc_mcp.client import BCMCPClient
from src.mcp.bc_mcp.config import BCMCPSettings


class _FakeCredential:
    def get_token(self, scope: str) -> SimpleNamespace:
        return SimpleNamespace(token=f"token-for:{scope}")


def test_bc_mcp_settings_defaults_match_project_configuration() -> None:
    settings = BCMCPSettings()

    assert settings.server_url == "https://mcp.businesscentral.dynamics.com"
    assert settings.tenant_id == "562029ef-9022-45a6-b255-40cd71ebb2ce"
    assert settings.environment_name == "Production"
    assert settings.company == "CRONUS USA, Inc."
    assert settings.configuration_name == "DefaultMCPKiko"


def test_prepare_arguments_merges_context_with_operation_payload() -> None:
    client = BCMCPClient(settings=BCMCPSettings(), credential=_FakeCredential())

    prepared = client._prepare_arguments({"top": 5})

    assert prepared["tenantId"] == "562029ef-9022-45a6-b255-40cd71ebb2ce"
    assert prepared["company"] == "CRONUS USA, Inc."
    assert prepared["top"] == 5


def test_parse_tool_result_prefers_structured_content() -> None:
    result = CallToolResult(content=[TextContent(type="text", text="ignored")], structuredContent={"value": []})

    assert BCMCPClient._parse_tool_result(result) == {"value": []}


def test_build_headers_uses_default_credential_scope() -> None:
    client = BCMCPClient(settings=BCMCPSettings(), credential=_FakeCredential())

    headers = client._build_headers()

    assert headers["Authorization"] == "Bearer token-for:https://mcp.businesscentral.dynamics.com/.default"
    assert headers["x-bc-configuration-name"] == "DefaultMCPKiko"
