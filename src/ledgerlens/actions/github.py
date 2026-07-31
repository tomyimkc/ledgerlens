"""Safety-gated GitHub issue creation adapter."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import quote

from pydantic import Field, JsonValue, SecretStr, field_validator

from .auth import ActionAuthorizer, Clock, utc_now
from .base import BaseActionAdapter, ReceiptFields
from .errors import ActionHTTPError
from .idempotency import IdempotencyStore
from .models import ActionPreview, BaseAction
from .transport import HttpRequest, HttpResponse, HttpTransport, RetryPolicy


class GitHubIssueAction(BaseAction):
    owner: str = Field(min_length=1, max_length=100)
    repository: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(default="", max_length=65_536)
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()

    @field_validator("owner", "repository")
    @classmethod
    def validate_path_segment(cls, value: str) -> str:
        if any(character in value for character in "/\r\n"):
            raise ValueError("GitHub owner and repository must be single path segments")
        return value

    @field_validator("labels", "assignees")
    @classmethod
    def deduplicate_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


class GitHubIssueAdapter(BaseActionAdapter[GitHubIssueAction]):
    """Create GitHub issues using a locally deduplicated, signed action."""

    name = "github"
    operation = "create_issue"
    action_type = GitHubIssueAction

    def __init__(
        self,
        token: str,
        *,
        authorizer: ActionAuthorizer,
        api_url: str = "https://api.github.com",
        api_version: str = "2022-11-28",
        transport: HttpTransport | None = None,
        idempotency_store: IdempotencyStore | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout: float = 8.0,
        clock: Clock = utc_now,
        sleep: Callable[[float], None] | None = None,
        random_source: Callable[[], float] | None = None,
    ) -> None:
        if not token:
            raise ValueError("GitHub token cannot be blank")
        self._token = SecretStr(token)
        self.api_url = api_url.rstrip("/")
        self.api_version = api_version
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

    def _target(self, action: GitHubIssueAction) -> str:
        return f"github:{action.owner}/{action.repository}"

    def _summary(self, action: GitHubIssueAction) -> str:
        return f"Create GitHub issue in {action.owner}/{action.repository}"

    def _preview_payload(self, action: GitHubIssueAction) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "owner": action.owner,
            "repository": action.repository,
            "title": action.title,
            "body": action.body,
        }
        if action.labels:
            payload["labels"] = list(action.labels)
        if action.assignees:
            payload["assignees"] = list(action.assignees)
        return payload

    def _build_request(
        self,
        action: GitHubIssueAction,
        preview: ActionPreview,
    ) -> HttpRequest:
        del preview
        url = (
            f"{self.api_url}/repos/{quote(action.owner, safe='')}/"
            f"{quote(action.repository, safe='')}/issues"
        )
        body: dict[str, JsonValue] = {"title": action.title, "body": action.body}
        if action.labels:
            body["labels"] = list(action.labels)
        if action.assignees:
            body["assignees"] = list(action.assignees)
        return HttpRequest(
            adapter=self.name,
            method="POST",
            url=url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token.get_secret_value()}",
                "X-GitHub-Api-Version": self.api_version,
                "User-Agent": "ledgerlens-action-adapter/0.1",
            },
            json_body=body,
            timeout=self.timeout,
        )

    def _parse_response(
        self,
        action: GitHubIssueAction,
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
        number = data.get("number")
        issue_id = data.get("id")
        remote_id = str(number if number is not None else issue_id) if data else None
        remote_url = data.get("html_url")
        details: dict[str, JsonValue] = {"repository": f"{action.owner}/{action.repository}"}
        if isinstance(number, int):
            details["number"] = number
        state = data.get("state")
        if isinstance(state, str):
            details["state"] = state
        return ReceiptFields(
            remote_id=remote_id,
            remote_url=remote_url if isinstance(remote_url, str) else None,
            details=details,
        )
