"""Bounded HTTP model adapters. No document bodies or secrets enter error messages."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError


class ProviderError(RuntimeError):
    def __init__(self, code: str, *, calls: list[dict] | None = None):
        self.code = code
        self.model_calls = calls or []
        super().__init__(code)


def gemini_schema(schema: dict) -> dict:
    """Translate bounded Pydantic schemas to a smaller provider-compatible JSON schema.

    Local validation retains every length/range bound removed from the wire schema.
    Gemini can reject complex nested bounded arrays with a bare INVALID_ARGUMENT.
    """
    definitions = schema.get("$defs", {})

    def visit(value, depth=0):
        if depth > 30:
            raise ProviderError("PROVIDER_SCHEMA_TOO_COMPLEX")
        if isinstance(value, list):
            return [visit(item, depth + 1) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            reference = value["$ref"]
            if not reference.startswith("#/$defs/") or reference.split("/")[-1] not in definitions:
                raise ProviderError("PROVIDER_SCHEMA_UNSUPPORTED")
            return visit(definitions[reference.split("/")[-1]], depth + 1)
        return {
            key: visit(item, depth + 1)
            for key, item in value.items()
            if key
            not in {"$defs", "title", "minimum", "maximum", "minLength", "maxLength", "maxItems", "minItems"}
        }

    return visit(schema)


@dataclass
class ModelProvider:
    name: str
    model: str
    key: str = field(repr=False)
    timeout: float = 40.0
    retries: int = 1
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None

    def request(self, system: str, prompt: str, schema: dict) -> tuple[str, dict, dict]:
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        """Shared tokenizer estimate; authoritative usage comes from provider responses."""
        from app.services.chunking import count_tokens

        return count_tokens(text)

    def health(self) -> dict:
        """Inspect current model availability without sending any source content."""
        if not self.key or not self.model:
            return {"available": False, "code": "PROVIDER_NOT_CONFIGURED"}
        endpoints = {
            "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
            "groq": "https://api.groq.com/openai/v1/models",
            "openrouter": "https://openrouter.ai/api/v1/models",
        }
        headers = (
            {"x-goog-api-key": self.key} if self.name == "gemini" else {"Authorization": f"Bearer {self.key}"}
        )
        try:
            with httpx.Client(
                timeout=min(self.timeout, 10), follow_redirects=False, trust_env=False
            ) as client:
                response = client.get(endpoints[self.name], headers=headers)
            if response.status_code != 200:
                return {"available": False, "code": "PROVIDER_UNAVAILABLE"}
            raw = response.json()
            entries = raw.get("models" if self.name == "gemini" else "data", [])
            entry = next(
                (
                    item
                    for item in entries
                    if item.get("id", item.get("name", "")).removeprefix("models/") == self.model
                ),
                None,
            )
            if entry is None:
                return {
                    "available": False,
                    "code": "MODEL_NOT_LISTED",
                    "complete_catalog": not bool(raw.get("nextPageToken")),
                }
            parameters = entry.get("supported_parameters")
            return {
                "available": True,
                "model": self.model,
                "structured_output_support": (
                    "response_format" in parameters or "structured_outputs" in parameters
                )
                if parameters is not None
                else None,
            }
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return {"available": False, "code": "PROVIDER_UNAVAILABLE"}

    def generate(
        self, system: str, prompt: str, schema_type: type[BaseModel], role: str
    ) -> tuple[BaseModel, list[dict]]:
        calls: list[dict] = []
        if not self.key or not self.model:
            raise ProviderError("PROVIDER_NOT_CONFIGURED")
        if len(system) + len(prompt) > 180000:
            raise ProviderError("PROVIDER_INPUT_BUDGET_EXCEEDED")
        for attempt in range(min(max(self.retries, 0), 2) + 1):
            started = time.monotonic()
            call = {
                "provider": self.name,
                "model": self.model,
                "role": role,
                "attempt": attempt + 1,
                "prompt_version": "evidence-v2.1.0",
                "token_in": None,
                "token_out": None,
                "estimated_cost": None,
            }
            retryable = False
            try:
                url, headers, payload = self.request(system, prompt, schema_type.model_json_schema())
                # Fixed provider URLs only. Ignore ambient proxies and never follow redirects.
                with httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
                    response = client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    retryable = response.status_code in {408, 429, 500, 502, 503, 504}
                    call["http_status"] = response.status_code
                    code = {
                        400: "PROVIDER_REQUEST_REJECTED",
                        401: "PROVIDER_AUTH_FAILED",
                        403: "PROVIDER_AUTH_FAILED",
                        404: "PROVIDER_MODEL_UNAVAILABLE",
                        422: "PROVIDER_REQUEST_REJECTED",
                        429: "PROVIDER_RATE_LIMITED",
                    }.get(response.status_code, "PROVIDER_UNAVAILABLE")
                    raise ProviderError(code)
                raw = response.json()
                call.update(
                    requested_model=self.model, response_model=raw.get("model", raw.get("modelVersion"))
                )
                content, token_in, token_out = self.unpack(raw)
                call.update(token_in=token_in, token_out=token_out)
                if (
                    token_in is not None
                    and token_out is not None
                    and self.input_price_per_million is not None
                    and self.output_price_per_million is not None
                ):
                    call["estimated_cost"] = (
                        token_in * self.input_price_per_million + token_out * self.output_price_per_million
                    ) / 1_000_000
                value = schema_type.model_validate_json(content)
                call["outcome"] = "SUCCESS"
                call["latency_ms"] = round((time.monotonic() - started) * 1000)
                calls.append(call)
                return value, calls
            except httpx.TimeoutException:
                code, retryable = "PROVIDER_TIMEOUT", True
            except httpx.HTTPError:
                code, retryable = "PROVIDER_UNAVAILABLE", True
            except (ValidationError, ValueError, KeyError, IndexError, TypeError):
                code, retryable = "PROVIDER_INVALID_OUTPUT", True
            except ProviderError as exc:
                code = exc.code
            call.update(outcome=code, latency_ms=round((time.monotonic() - started) * 1000))
            calls.append(call)
            if not retryable or attempt >= min(max(self.retries, 0), 2):
                raise ProviderError(code, calls=calls) from None
            time.sleep(min(2**attempt, 4) + random.uniform(0, 0.2))
        raise ProviderError("PROVIDER_UNAVAILABLE", calls=calls)

    def unpack(self, raw: dict) -> tuple[str, int | None, int | None]:
        choice = raw["choices"][0]
        if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
            raise ProviderError("PROVIDER_INCOMPLETE_OUTPUT")
        usage = raw.get("usage", {})
        return choice["message"]["content"], usage.get("prompt_tokens"), usage.get("completion_tokens")


class CompatibleProvider(ModelProvider):
    def request(self, system: str, prompt: str, schema: dict) -> tuple[str, dict, dict]:
        endpoints = {
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 4096,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "veriora_output", "strict": True, "schema": schema},
            },
        }
        if self.name == "openrouter":
            # Prevent OpenRouter's internal model fallback and require schema capability.
            payload["provider"] = {"require_parameters": True, "allow_fallbacks": False}
        return endpoints[self.name], {"Authorization": f"Bearer {self.key}"}, payload


class GeminiProvider(ModelProvider):
    def request(self, system: str, prompt: str, schema: dict) -> tuple[str, dict, dict]:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.model):
            raise ProviderError("PROVIDER_INVALID_MODEL")
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": self.key},
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 4096,
                    "responseMimeType": "application/json",
                    "responseJsonSchema": gemini_schema(schema),
                },
            },
        )

    def unpack(self, raw: dict) -> tuple[str, int | None, int | None]:
        candidate = raw["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ProviderError("PROVIDER_INCOMPLETE_OUTPUT")
        content = "".join(
            part.get("text", "") for part in candidate["content"]["parts"] if not part.get("thought")
        )
        usage = raw.get("usageMetadata", {})
        return content, usage.get("promptTokenCount"), usage.get("candidatesTokenCount")


def configured_provider(config: dict) -> ModelProvider:
    name = config.get("name", "")
    if name not in {"gemini", "groq", "openrouter"}:
        raise ProviderError("PROVIDER_NOT_SUPPORTED")
    cls = GeminiProvider if name == "gemini" else CompatibleProvider
    return cls(
        name=name,
        model=config.get("model", ""),
        key=config.get("key", ""),
        timeout=min(float(config.get("timeout", 40)), 60),
        retries=int(config.get("retries", 1)),
        input_price_per_million=config.get("input_price_per_million"),
        output_price_per_million=config.get("output_price_per_million"),
    )


def generate_with_fallback(
    configs: list[dict], system: str, prompt: str, schema_type: type[BaseModel], role: str
) -> tuple[BaseModel, list[dict]]:
    """Only the caller's explicit consent-filtered list may receive document text."""
    if not configs:
        raise ProviderError("PROVIDER_NOT_CONFIGURED")
    calls: list[dict] = []
    last_code = "PROVIDER_NOT_CONFIGURED"
    for index, config in enumerate(configs[:3]):
        try:
            value, new_calls = configured_provider(config).generate(system, prompt, schema_type, role)
            for call in new_calls:
                call["fallback"] = index > 0
            calls.extend(new_calls)
            return value, calls
        except ProviderError as exc:
            last_code = exc.code
            for call in exc.model_calls:
                call["fallback"] = index > 0
            calls.extend(exc.model_calls)
    raise ProviderError(last_code, calls=calls)
