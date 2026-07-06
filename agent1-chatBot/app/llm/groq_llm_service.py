"""
app/llm/groq_llm_service.py

WHY THIS FILE EXISTS
---------------------
Exactly ONE class in this codebase is allowed to import `groq`
directly. Implements the "Groq LLM" pipeline stage as a single,
general-purpose `generate_completion(...)` method - deliberately NOT
specialized to "answer this RAG question", since the spec also needs
Groq for Follow-up Question Generation (upcoming `suggestions/`
folder). Both use cases send a `messages` list and get back a
normalized `LLMResponse`; only the MESSAGES differ (built by
`prompts/` for QA, or by `suggestions/` for follow-ups), never this
service's logic.

WHY every Groq SDK exception is mapped to one of THIS service's own
typed exceptions (`GroqTimeoutError` / `GroqRateLimitError` /
`GroqAuthenticationError` / `GroqAPIError`) rather than letting raw
`groq.*Error` exceptions propagate: identical rationale to every other
service in this codebase - `core/exception_handlers.py` only knows how
to translate `IntelliPlantBaseException` subclasses into the
standard error envelope. A raw `groq.RateLimitError` escaping this
service would bypass that entirely and fall through to the generic
500 handler, losing the 429 status and retry semantics callers need.

WHY this service implements its OWN retry loop rather than relying on
the Groq SDK's built-in `max_retries`: the SDK's built-in retries are
opaque - callers can't observe or log individual attempts, and it
retries indiscriminately across error types. This service's retry
loop is explicit about WHICH errors are retryable (timeouts, transient
connection errors, 5xx) versus which are NOT (auth failures, rate
limits, bad requests) - retrying an invalid API key or a 429 without
backoff wastes the retry budget on failures no retry could ever fix
or would only make worse. The underlying SDK client is constructed
with `max_retries=0` specifically to prevent the two retry layers
from compounding into surprising total delays.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import (
    GroqAPIError,
    GroqAuthenticationError,
    GroqRateLimitError,
    GroqTimeoutError,
)
from app.llm.schemas import LLMResponse

# WHY a fixed, small base delay with simple exponential backoff (not a
# more elaborate jittered/adaptive scheme): GROQ_MAX_RETRIES defaults
# to 2, so at most 2 retries ever happen - the delay curve only needs
# to give a transient blip (a dropped connection, a momentary 503) a
# reasonable chance to clear, not implement a sophisticated backoff
# policy for a retry budget this small.
_RETRY_BASE_DELAY_SECONDS = 0.5


def _default_client_factory(settings: Settings) -> Any:
    """
    Production Groq client factory. Import kept local for the same
    reason as every other service's default loader in this codebase:
    avoid the import cost for code paths (or tests) that inject a fake
    client and never need the real `groq` package touched at all.

    WHY `max_retries=0`: see module docstring - this service owns
    retry policy itself.
    """
    import groq

    return groq.Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=settings.GROQ_TIMEOUT_SECONDS,
        max_retries=0,
    )


class GroqLLMService(BaseService):
    """
    Wraps the Groq chat completions API with typed error handling,
    explicit retry policy, and a normalized response shape.
    """

    def __init__(
        self,
        settings: Settings,
        client_factory: Optional[Callable[[Settings], Any]] = None,
    ) -> None:
        """
        Args:
            settings: Validated application settings - specifically
                GROQ_API_KEY, GROQ_MODEL, GROQ_TEMPERATURE,
                GROQ_MAX_TOKENS, GROQ_TIMEOUT_SECONDS, GROQ_MAX_RETRIES.
            client_factory: Optional factory `(settings) -> groq-client-
                like object`. Defaults to `_default_client_factory`.
                Tests inject a fake client exposing
                `chat.completions.create(...)` to validate this
                service's retry/error-mapping/parsing logic without
                real network access to Groq.
        """
        super().__init__(settings)
        self._client_factory = client_factory or _default_client_factory
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory(self.settings)
        return self._client

    def generate_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Send a chat completion request to Groq, with typed error
        handling and automatic retry on transient failures.

        Args:
            messages: Chat messages in `{"role": ..., "content": ...}`
                format - typically built by
                `PromptBuilderService.build_messages(...)` for QA, or
                by the follow-up generator (upcoming `suggestions/`
                folder) for a different prompt.
            model: Override for `Settings.GROQ_MODEL`.
            temperature: Override for `Settings.GROQ_TEMPERATURE`.
            max_tokens: Override for `Settings.GROQ_MAX_TOKENS`.

        Returns:
            A normalized `LLMResponse`.

        Raises:
            GroqAuthenticationError: invalid/expired API key - never
                retried.
            GroqRateLimitError: Groq rate-limited this request - never
                retried by this service (the 429 status is surfaced so
                the CALLER/orchestrator can decide on backoff policy
                at a higher level, e.g. across multiple agents sharing
                one Groq quota).
            GroqTimeoutError: the request exceeded
                `GROQ_TIMEOUT_SECONDS`, or a transient connection error
                did not resolve within `GROQ_MAX_RETRIES` attempts.
            GroqAPIError: any other Groq-side failure (5xx, malformed
                response) that did not resolve within
                `GROQ_MAX_RETRIES` attempts.
        """
        import groq  # local import - see _default_client_factory rationale

        effective_model = model or self.settings.GROQ_MODEL
        effective_temperature = (
            temperature if temperature is not None else self.settings.GROQ_TEMPERATURE
        )
        effective_max_tokens = max_tokens or self.settings.GROQ_MAX_TOKENS
        max_attempts = self.settings.GROQ_MAX_RETRIES + 1

        client = self._get_client()
        last_retryable_exception: Optional[BaseException] = None

        for attempt in range(1, max_attempts + 1):
            start = time.perf_counter()
            try:
                response = client.chat.completions.create(
                    model=effective_model,
                    messages=messages,
                    temperature=effective_temperature,
                    max_tokens=effective_max_tokens,
                )
            except groq.AuthenticationError as exc:
                # WHY never retried: an invalid/expired API key will
                # fail identically on every retry attempt - retrying
                # only burns the retry budget and delays surfacing a
                # failure that needs a human (rotate the key), not a
                # backoff, to fix.
                raise GroqAuthenticationError(
                    "Groq rejected the configured API key.",
                    stage=PipelineStage.LLM_GENERATION,
                    original_exception=exc,
                ) from exc
            except groq.RateLimitError as exc:
                raise GroqRateLimitError(
                    "Groq rate-limited this request.",
                    stage=PipelineStage.LLM_GENERATION,
                    details={"attempt": attempt},
                    original_exception=exc,
                ) from exc
            except groq.BadRequestError as exc:
                # WHY treated as non-retryable GroqAPIError rather than
                # a distinct exception type: a 400 means the REQUEST
                # ITSELF is malformed (e.g. an invalid model name, a
                # messages list that violates Groq's schema) - retrying
                # the identical request will fail identically every
                # time, exactly like an auth failure.
                raise GroqAPIError(
                    "Groq rejected the request as malformed.",
                    stage=PipelineStage.LLM_GENERATION,
                    details={"attempt": attempt},
                    original_exception=exc,
                ) from exc
            except (groq.APITimeoutError, groq.APIConnectionError) as exc:
                last_retryable_exception = exc
                if attempt < max_attempts:
                    backoff = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    self.logger.bind(stage=PipelineStage.LLM_GENERATION.value).warning(
                        f"Groq request timed out/failed to connect "
                        f"(attempt {attempt}/{max_attempts}) - retrying in "
                        f"{backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
                raise GroqTimeoutError(
                    f"Groq did not respond within "
                    f"{self.settings.GROQ_TIMEOUT_SECONDS}s after "
                    f"{max_attempts} attempt(s).",
                    stage=PipelineStage.LLM_GENERATION,
                    details={"attempts": max_attempts},
                    original_exception=exc,
                ) from exc
            except (groq.InternalServerError, groq.APIStatusError) as exc:
                last_retryable_exception = exc
                if attempt < max_attempts:
                    backoff = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    self.logger.bind(stage=PipelineStage.LLM_GENERATION.value).warning(
                        f"Groq returned a server error (attempt "
                        f"{attempt}/{max_attempts}) - retrying in {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
                raise GroqAPIError(
                    f"Groq returned a server error after {max_attempts} "
                    f"attempt(s).",
                    stage=PipelineStage.LLM_GENERATION,
                    details={"attempts": max_attempts},
                    original_exception=exc,
                ) from exc
            except Exception as exc:
                # WHY this final catch-all is NOT retried: an exception
                # type this service doesn't specifically recognize is
                # unexpected by definition - retrying blindly into the
                # unknown risks masking a real bug (e.g. a parsing
                # error in OUR code, not Groq's) as if it were a
                # transient network issue.
                raise GroqAPIError(
                    "An unexpected error occurred while calling Groq.",
                    stage=PipelineStage.LLM_GENERATION,
                    original_exception=exc,
                ) from exc
            else:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return self._parse_response(response, elapsed_ms)

        # WHY this line is unreachable in practice (every branch above
        # either `return`s or `raise`s) but still present: satisfies
        # static analysis that this function always returns/raises,
        # and gives a clear, specific error if the loop's invariants
        # are ever violated by a future edit, rather than an implicit
        # `None` silently propagating as a fake "successful" response.
        raise GroqAPIError(
            "Exhausted all retry attempts without a successful response or "
            "a specific error.",
            stage=PipelineStage.LLM_GENERATION,
            original_exception=last_retryable_exception,
        )

    def _parse_response(self, response: Any, elapsed_ms: float) -> LLMResponse:
        """
        Convert a raw Groq `ChatCompletion` object into a normalized
        `LLMResponse`.

        WHY this is its own method rather than inlined into
        `generate_completion`: keeps response-shape parsing testable
        and readable independent of the retry loop's control flow, and
        gives future response-format changes (e.g. Groq adding new
        usage fields) exactly one place to update.
        """
        try:
            choice = response.choices[0]
            usage = response.usage
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                finish_reason=choice.finish_reason or "unknown",
                latency_ms=elapsed_ms,
            )
        except (AttributeError, IndexError, TypeError) as exc:
            raise GroqAPIError(
                "Groq returned a response in an unexpected shape.",
                stage=PipelineStage.LLM_GENERATION,
                original_exception=exc,
            ) from exc

    def health_check(self) -> dict:
        """
        Verifies Groq is reachable and configured correctly by sending
        a minimal, cheap probe completion.

        WHY a real (tiny) completion call rather than just checking
        `GROQ_API_KEY` is non-empty: an API key can be present but
        still invalid/expired/revoked, or the model name could be
        misconfigured - only an actual round-trip proves the LLM stage
        is truly functional, matching every other service's health
        check philosophy in this codebase.
        """
        try:
            response = self.generate_completion(
                [{"role": "user", "content": "Respond with exactly: OK"}],
                max_tokens=5,
            )
            return {
                "service": self.service_name,
                "healthy": True,
                "details": {
                    "model": response.model,
                    "probe_latency_ms": round(response.latency_ms, 2),
                },
            }
        except (GroqAuthenticationError, GroqRateLimitError, GroqTimeoutError, GroqAPIError) as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message, "error_code": exc.error_code.value},
            }
