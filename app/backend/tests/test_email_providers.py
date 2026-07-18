from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import HTTPException

import email_generation
from email_generation import (
    EMAIL_INSTRUCTIONS,
    GEMINI_EMAIL_RESPONSE_SCHEMA,
    GeminiEmailGenerator,
    GeneratedEmail,
    OpenAIEmailGenerator,
    ProviderUnavailableError,
    get_email_generator,
)


class FakeOpenAIResponses:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return SimpleNamespace(output_text=self.output)


class FakeOpenAIClient:
    def __init__(self, output: object) -> None:
        self.responses = FakeOpenAIResponses(output)


class FakeGeminiModels:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return SimpleNamespace(text=self.output)


class FakeGeminiClient:
    def __init__(self, output: object) -> None:
        self.models = FakeGeminiModels(output)


def test_email_instructions_define_srushtis_personalized_outreach_voice() -> None:
    assert "natural voice" in EMAIL_INSTRUCTIONS
    assert "generic AI-written" in EMAIL_INSTRUCTIONS
    assert "Hello [Recipient Name]," in EMAIL_INSTRUCTIONS
    assert "specific reference" in EMAIL_INSTRUCTIONS
    assert "A few relevant highlights:" in EMAIL_INSTRUCTIONS
    assert '"•" character' in EMAIL_INSTRUCTIONS
    assert "preview, not a full resume dump" in EMAIL_INSTRUCTIONS
    assert "confident, low-pressure invitation" in EMAIL_INSTRUCTIONS
    assert "Do not force humor" in EMAIL_INSTRUCTIONS
    assert "career-trailer metaphors" in EMAIL_INSTRUCTIONS
    assert "Best regards,\nSrushti Shinde" in EMAIL_INSTRUCTIONS


def _configure(monkeypatch: pytest.MonkeyPatch, **values: str | None) -> None:
    for name in (
        "AI_PROVIDER",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        if value is not None:
            monkeypatch.setenv(name, value)


def test_selects_gemini_without_openai_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        AI_PROVIDER=" Gemini ",
        GEMINI_API_KEY="gemini-key",
        GEMINI_MODEL="gemini-2.5-flash",
    )

    generator = get_email_generator()

    assert isinstance(generator, GeminiEmailGenerator)


def test_selects_openai_without_gemini_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        AI_PROVIDER="OPENAI",
        OPENAI_API_KEY="openai-key",
        OPENAI_MODEL="gpt-test",
    )

    generator = get_email_generator()

    assert isinstance(generator, OpenAIEmailGenerator)


@pytest.mark.parametrize(
    ("values"),
    [
        {"AI_PROVIDER": "unsupported"},
        {"AI_PROVIDER": "gemini", "GEMINI_MODEL": "gemini-2.5-flash"},
        {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "key"},
        {"AI_PROVIDER": "openai", "OPENAI_MODEL": "gpt-test"},
        {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "key"},
    ],
)
def test_rejects_invalid_active_provider_configuration(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, str]
) -> None:
    _configure(monkeypatch, **values)

    with pytest.raises(HTTPException) as error:
        get_email_generator()

    assert error.value.status_code == 503
    assert error.value.detail == "Email generation is not configured."


@pytest.mark.parametrize(
    ("generator_class", "client_name"),
    [(GeminiEmailGenerator, "Gemini"), (OpenAIEmailGenerator, "OpenAI")],
)
def test_providers_return_validated_structured_email(
    monkeypatch: pytest.MonkeyPatch,
    generator_class: type[GeminiEmailGenerator] | type[OpenAIEmailGenerator],
    client_name: str,
) -> None:
    output = '{"subject": "Hello", "body": "Email body"}'
    client: FakeGeminiClient | FakeOpenAIClient
    if client_name == "Gemini":
        client = FakeGeminiClient(output)
        monkeypatch.setattr(email_generation.genai, "Client", lambda **_kwargs: client)
    else:
        client = FakeOpenAIClient(output)
        monkeypatch.setattr(email_generation, "OpenAI", lambda **_kwargs: client)

    result = generator_class("test-key", "test-model").generate("safe prompt")

    assert result == GeneratedEmail(subject="Hello", body="Email body")
    if client_name == "Gemini":
        gemini_client = cast(FakeGeminiClient, client)
        assert gemini_client.models.calls[0]["model"] == "test-model"
        config = cast(Any, gemini_client.models.calls[0]["config"])
        assert config.response_mime_type == "application/json"
        assert config.response_schema == GEMINI_EMAIL_RESPONSE_SCHEMA
        assert "additionalProperties" not in config.response_schema
    else:
        openai_client = cast(FakeOpenAIClient, client)
        assert openai_client.responses.calls[0]["model"] == "test-model"
        assert openai_client.responses.calls[0]["text"] is not None


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        "[]",
        '{"body": "Email body"}',
        '{"subject": "Hello"}',
        '{"subject": " ", "body": "Email body"}',
        '{"subject": "Hello", "body": " "}',
        '{"subject": null, "body": "Email body"}',
        '{"subject": 1, "body": "Email body"}',
    ],
)
@pytest.mark.parametrize("provider", ["gemini", "openai"])
def test_providers_reject_malformed_or_incomplete_output(
    monkeypatch: pytest.MonkeyPatch, provider: str, output: str
) -> None:
    generator: GeminiEmailGenerator | OpenAIEmailGenerator
    if provider == "gemini":
        monkeypatch.setattr(
            email_generation.genai,
            "Client",
            lambda **_kwargs: FakeGeminiClient(output),
        )
        generator = GeminiEmailGenerator("key", "model")
    else:
        monkeypatch.setattr(
            email_generation,
            "OpenAI",
            lambda **_kwargs: FakeOpenAIClient(output),
        )
        generator = OpenAIEmailGenerator("key", "model")

    with pytest.raises(ValueError, match="Provider returned an invalid response"):
        generator.generate("safe prompt")


@pytest.mark.parametrize("provider", ["gemini", "openai"])
def test_provider_exception_is_safe_at_the_boundary(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    sensitive_error = RuntimeError("raw provider response contains secret-like text")
    generator: GeminiEmailGenerator | OpenAIEmailGenerator
    if provider == "gemini":
        monkeypatch.setattr(
            email_generation.genai,
            "Client",
            lambda **_kwargs: FakeGeminiClient(sensitive_error),
        )
        generator = GeminiEmailGenerator("key", "model")
    else:
        monkeypatch.setattr(
            email_generation,
            "OpenAI",
            lambda **_kwargs: FakeOpenAIClient(sensitive_error),
        )
        generator = OpenAIEmailGenerator("key", "model")

    with pytest.raises(ProviderUnavailableError) as error:
        generator.generate("safe prompt")

    assert str(error.value) == ""


def test_gemini_uses_api_compatible_schema_and_safe_diagnostics(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class GeminiClientError(Exception):
        code = 400
        message = (
            'Invalid JSON payload received: unknown field "additional_properties".'
        )

    monkeypatch.setattr(
        email_generation.genai,
        "Client",
        lambda **_kwargs: FakeGeminiClient(GeminiClientError()),
    )

    with pytest.raises(ProviderUnavailableError):
        GeminiEmailGenerator("key", "gemini-3-flash-preview").generate(
            "resume_text: sensitive prompt"
        )

    assert "provider=gemini" in caplog.text
    assert "status_code=400" in caplog.text
    assert "category=provider" in caplog.text
    assert "unknown field" in caplog.text
    assert "resume_text" not in caplog.text
    assert "sensitive prompt" not in caplog.text
