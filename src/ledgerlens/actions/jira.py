"""Safety-gated Jira Cloud REST v3 issue creation adapter."""

from __future__ import annotations

import base64
from collections.abc import Callable

from pydantic import Field, JsonValue, SecretStr, field_validator

from .auth import ActionAuthorizer, Clock, utc_now
from .base import BaseActionAdapter, ReceiptFields
from .errors import ActionHTTPError
from .idempotency import IdempotencyStore
from .models import ActionPreview, BaseAction
from .transport import HttpRequest, HttpResponse, HttpTransport, RetryPolicy


class JiraIssueAction(BaseAction):
    project_key: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=100_000)
    issue_type: str = Field(default="Task", min_length=1, max_length=128)
    labels: tuple[str, ...] = ()

    @field_validator("project_key")
    @classmethod
    def validate_project_key(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("Jira project_key must be alphanumeric or underscore")
        return value

    @field_validator("labels")
    @classmethod
    def deduplicate_labels(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


class JiraIssueAdapter(BaseActionAdapter[JiraIssueAction]):
    """Create Jira issues using basic API-token or bearer authentication."""

    name = "jira"
    operation = "create_issue"
    action_type = JiraIssueAction

    def __init__(
        self,
        site_url: str,
        *,
        authorizer: ActionAuthorizer,
        email: str | None = None,
        api_token: str | None = None,
        bearer_token: str | None = None,
        transport: HttpTransport | None = None,
        idempotency_store: IdempotencyStore | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout: float = 8.0,
        clock: Clock = utc_now,
        sleep: Callable[[float], None] | None = None,
        random_source: Callable[[], float] | None = None,
    ) -> None:
        has_basic = bool(email and api_token)
        has_bearer = bool(bearer_token)
        if has_basic == has_bearer:
            raise ValueError(
                "configure exactly one Jira auth mode: email+api_token or bearer_token"
            )
        if bool(email) != bool(api_token):
            raise ValueError("Jira email and api_token must be provided together")
        self.site_url = site_url.rstrip("/")
        self._email = email
        self._api_token = SecretStr(api_token) if api_token else None
        self._bearer_token = SecretStr(bearer_token) if bearer_token else None
        super().__init__(
            authorizer=authorizer,
            transport=transport,
            idempotency_store=idempotency_store,
            retry_policy=retry_policy,
            timeout=timeout,
            clock=clock,
            sleep=sleep,
            random_source=random_source,
        )

    def _target(self, action: JiraIssueAction) -> str:
        return f"jira:project:{action.project_key}"

    def _summary(self, action: JiraIssueAction) -> str:
        return f"Create Jira issue in project {action.project_key}"

    def _preview_payload(self, action: JiraIssueAction) -> dict[str, JsonValue]:
        fields: dict[str, JsonValue] = {
            "project": {"key": action.project_key},
            "summary": action.summary,
            "issuetype": {"name": action.issue_type},
        }
        if action.description is not None:
            fields["description"] = _adf_text(action.description)
        if action.labels:
            fields["labels"] = list(action.labels)
        return {"fields": fields}

    def _build_request(
        self,
        action: JiraIssueAction,
        preview: ActionPreview,
    ) -> HttpRequest:
        del action
        return HttpRequest(
            adapter=self.name,
            method="POST",
            url=f"{self.site_url}/rest/api/3/issue",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": self._authorization_header(),
            },
            json_body=preview.payload,
            timeout=self.timeout,
        )

    def _parse_response(
        self,
        action: JiraIssueAction,
        preview: ActionPreview,
        response: HttpResponse,
        attempts: int,
    ) -> ReceiptFields:
        del preview
        if response.status_code != 201:
            raise ActionHTTPError(
                self.name,
                response.status_code,
                attempts=attempts,
                retryable=response.status_code >= 500 or response.status_code == 429,
            )
        data = response.json_body if isinstance(response.json_body, dict) else {}
        issue_key = data.get("key")
        issue_id = data.get("id")
        remote_id = issue_key if isinstance(issue_key, str) else None
        if remote_id is None and issue_id is not None:
            remote_id = str(issue_id)
        details: dict[str, JsonValue] = {"project_key": action.project_key}
        if isinstance(issue_key, str):
            details["issue_key"] = issue_key
        return ReceiptFields(
            remote_id=remote_id,
            remote_url=(
                f"{self.site_url}/browse/{issue_key}" if isinstance(issue_key, str) else None
            ),
            details=details,
        )

    def _authorization_header(self) -> str:
        if self._bearer_token is not None:
            return f"Bearer {self._bearer_token.get_secret_value()}"
        assert self._email is not None
        assert self._api_token is not None
        raw = f"{self._email}:{self._api_token.get_secret_value()}".encode()
        return "Basic " + base64.b64encode(raw).decode("ascii")


def _adf_text(description: str) -> dict[str, JsonValue]:
    content: list[JsonValue] = []
    for line in description.splitlines() or [""]:
        paragraph_content: list[JsonValue] = []
        if line:
            paragraph_content.append({"type": "text", "text": line})
        content.append({"type": "paragraph", "content": paragraph_content})
    return {"type": "doc", "version": 1, "content": content}
