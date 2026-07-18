import json
import logging
import os
import re
from typing import Annotated, Any, Protocol
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from google import genai
from google.genai import types
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from auth import AuthenticatedUser, get_current_user
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1", tags=["email generation"])
logger = logging.getLogger(__name__)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SENSITIVE_PROVIDER_MESSAGE_PATTERN = re.compile(
    r"(?:api[_ -]?key|authorization|bearer|resume_text|linkedin_post_text|"
    r"job_description_text|contents|prompt|input)",
    re.IGNORECASE,
)

EMAIL_INSTRUCTIONS = """Write one concise, personalized job-outreach email in Srushti's
natural voice: human, casual, informal, technically credible, and professional
enough for a hiring manager. Make it memorable rather than a generic AI-written
cover letter. Use only the resume and user inputs supplied. Never invent
experience, metrics, technologies, company facts, or recipient facts. Never
claim the recipient is hiring unless the supplied text says so.

Use this body structure and keep the paragraphs short with readable spacing:
1. Start with "Hello [Recipient Name]," when a recipient name is supplied;
   otherwise use "Hello,".
2. Open with a specific reference to the supplied LinkedIn post, company,
   product, role, or job description. Add a light, playful hook only when it
   fits naturally and is supported by that context.
3. Briefly explain why the opportunity caught Srushti's attention.
4. Introduce only the resume experience that is useful for this role.
5. Add a "A few relevant highlights:" section with two or three concise bullet
   points using the "•" character. Each point must be a supported, relevant
   resume achievement; this is a preview, not a full resume dump.
6. Optionally add one subtle creative line when it naturally fits the supplied
   company, role, or product context. Do not force humor or reuse movie, season,
   or career-trailer metaphors.
7. End with a confident, low-pressure invitation to have a short conversation.

Return only an object matching the requested schema. Include this exact signature
in the body:

Best regards,
Srushti Shinde
Phone: (608) 217-2116
LinkedIn: https://www.linkedin.com/in/srushtisanjayshinde/"""


class EmailGenerationRequest(BaseModel):
    resume_id: UUID
    linkedin_post_text: str = ""
    job_description_text: str = ""
    no_job_description: bool = False
    recipient_to: str
    recipient_cc: str | None = None
    recipient_name: str | None = None
    company_name: str | None = None

    @field_validator("recipient_to")
    @classmethod
    def validate_required_email(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value or not EMAIL_PATTERN.fullmatch(normalized_value):
            raise ValueError("Enter a valid email address.")
        return normalized_value

    @field_validator("recipient_cc")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized_value = value.strip()
        if not EMAIL_PATTERN.fullmatch(normalized_value):
            raise ValueError("Enter a valid email address.")
        return normalized_value

    @model_validator(mode="after")
    def validate_inputs(self) -> "EmailGenerationRequest":
        has_linkedin_text = bool(self.linkedin_post_text.strip())
        has_job_description = bool(self.job_description_text.strip())
        if not has_linkedin_text and not has_job_description:
            raise ValueError("Add LinkedIn post text or a job description.")
        if not has_job_description and not self.no_job_description:
            raise ValueError(
                "Select 'No job description available' when no job description "
                "is provided."
            )
        return self


class GeneratedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)

    @field_validator("subject", "body")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Email fields must not be blank.")
        return value


# Keep this schema deliberately within Gemini's response-schema subset. Passing
# GeneratedEmail directly makes the SDK serialize Pydantic's
# ``additionalProperties: false`` as ``additional_properties``, which Gemini
# Developer API rejects for the configured model.
GEMINI_EMAIL_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["subject", "body"],
}


class ProviderUnavailableError(Exception):
    """A provider request failed without exposing provider details to clients."""


class EmailGenerator(Protocol):
    def generate(self, prompt: str) -> GeneratedEmail: ...


def build_generation_prompt(resume_text: str, request: EmailGenerationRequest) -> str:
    return json.dumps(
        {
            "resume_text": resume_text,
            "linkedin_post_text": request.linkedin_post_text,
            "job_description_text": request.job_description_text,
            "no_job_description": request.no_job_description,
            "recipient_name": request.recipient_name,
            "company_name": request.company_name,
        }
    )


def validate_generated_email(raw_output: object) -> GeneratedEmail:
    if not isinstance(raw_output, str):
        raise ValueError("Provider returned an invalid response.")
    try:
        parsed_response = json.loads(raw_output)
        return GeneratedEmail.model_validate(parsed_response)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Provider returned an invalid response.") from error


def _provider_error_category(error: Exception) -> str:
    status_code = _provider_status_code(error)
    error_name = type(error).__name__.lower()
    if status_code == 429 or "ratelimit" in error_name:
        return "rate_limit"
    if status_code in {401, 403} or "authentication" in error_name:
        return "authentication"
    if "timeout" in error_name or "connection" in error_name:
        return "network"
    return "provider"


def _provider_status_code(error: Exception) -> int | None:
    for attribute in ("status_code", "code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _sanitized_provider_message(error: Exception) -> str:
    message = getattr(error, "message", None)
    if not isinstance(message, str) or not message.strip():
        message = str(error)
    message = " ".join(message.split())
    if not message or SENSITIVE_PROVIDER_MESSAGE_PATTERN.search(message):
        return "Provider returned an error."
    return message[:500]


def _provider_unavailable(provider: str, error: Exception) -> ProviderUnavailableError:
    logger.warning(
        "Email generation provider failure provider=%s status_code=%s category=%s "
        "message=%s",
        provider,
        _provider_status_code(error),
        _provider_error_category(error),
        _sanitized_provider_message(error),
    )
    return ProviderUnavailableError()


class OpenAIEmailGenerator:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> GeneratedEmail:
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=EMAIL_INSTRUCTIONS,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "outreach_email",
                        "strict": True,
                        "schema": GeneratedEmail.model_json_schema(),
                    }
                },
            )
        except Exception as error:
            raise _provider_unavailable("openai", error) from error
        return validate_generated_email(response.output_text)


class GeminiEmailGenerator:
    def __init__(self, api_key: str, model: str) -> None:
        self._client: Any = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> GeneratedEmail:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EMAIL_INSTRUCTIONS,
                    response_mime_type="application/json",
                    response_schema=GEMINI_EMAIL_RESPONSE_SCHEMA,
                ),
            )
        except Exception as error:
            raise _provider_unavailable("gemini", error) from error
        return validate_generated_email(response.text)


def _configured_value(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def get_email_generator() -> EmailGenerator:
    provider = (_configured_value("AI_PROVIDER") or "").lower()
    if provider == "gemini":
        api_key = _configured_value("GEMINI_API_KEY")
        model = _configured_value("GEMINI_MODEL")
        if api_key and model:
            return GeminiEmailGenerator(api_key, model)
    elif provider == "openai":
        api_key = _configured_value("OPENAI_API_KEY")
        model = _configured_value("OPENAI_MODEL")
        if api_key and model:
            return OpenAIEmailGenerator(api_key, model)

    logger.warning("Email generation configuration invalid provider=%s", provider)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Email generation is not configured.",
    )


Generator = Annotated[EmailGenerator, Depends(get_email_generator)]


@router.post("/email-generation", response_model=GeneratedEmail)
def generate_email(
    request: EmailGenerationRequest,
    user: CurrentUser,
    storage: Storage,
    generator: Generator,
) -> GeneratedEmail:
    try:
        resume = storage.get_resume(str(request.resume_id), user["user_id"])
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The selected resume could not be loaded.",
        ) from error
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The selected resume was not found.",
        )

    extracted_text = resume.get("extracted_text")
    if resume.get("parse_status") != "completed" or not isinstance(extracted_text, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The selected resume is not ready for email generation.",
        )

    try:
        return generator.generate(build_generation_prompt(extracted_text, request))
    except ProviderUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email generation is temporarily unavailable. Please try again.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email generation returned an invalid response. Please try again.",
        ) from error
