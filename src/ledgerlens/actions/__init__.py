"""Safety-gated adapters for external incident-response actions."""

from .auth import ActionAuthorization, ActionAuthorizer
from .base import ActionAdapter, BaseActionAdapter
from .errors import (
    ActionAuthorizationError,
    ActionError,
    ActionHTTPError,
    ActionIndeterminateError,
    ActionInProgressError,
    ActionOutcomeUnknownError,
    ActionProviderError,
    ActionTransportError,
    ActionValidationError,
    IdempotencyConflictError,
    IdempotencyError,
)
from .fanout import (
    ActionFailure,
    ActionFanoutExecutor,
    ActionFanoutItem,
    ActionFanoutReport,
    ActionInvocation,
)
from .github import GitHubIssueAction, GitHubIssueAdapter
from .idempotency import (
    IdempotencyClaim,
    IdempotencyState,
    IdempotencyStore,
    InMemoryIdempotencyStore,
    SQLiteIdempotencyStore,
)
from .jira import JiraIssueAction, JiraIssueAdapter
from .models import ActionExecutionStatus, ActionPreview, ActionReceipt, BaseAction
from .pagerduty import (
    PagerDutyEventAction,
    PagerDutyEventActionType,
    PagerDutyEventsAdapter,
    PagerDutySeverity,
)
from .slack import SlackAdapter, SlackMessageAction, SlackMode
from .transport import (
    HttpRequest,
    HttpResponse,
    HttpTransport,
    HttpxTransport,
    RetryingHttpExecutor,
    RetryPolicy,
    TransportConnectionFailure,
    TransportFailure,
    TransportTimeoutFailure,
)

__all__ = [
    "ActionAdapter",
    "ActionAuthorization",
    "ActionAuthorizationError",
    "ActionAuthorizer",
    "ActionError",
    "ActionExecutionStatus",
    "ActionFailure",
    "ActionFanoutExecutor",
    "ActionFanoutItem",
    "ActionFanoutReport",
    "ActionHTTPError",
    "ActionIndeterminateError",
    "ActionInProgressError",
    "ActionInvocation",
    "ActionOutcomeUnknownError",
    "ActionPreview",
    "ActionProviderError",
    "ActionReceipt",
    "ActionTransportError",
    "ActionValidationError",
    "BaseAction",
    "BaseActionAdapter",
    "GitHubIssueAction",
    "GitHubIssueAdapter",
    "HttpRequest",
    "HttpResponse",
    "HttpTransport",
    "HttpxTransport",
    "IdempotencyClaim",
    "IdempotencyConflictError",
    "IdempotencyError",
    "IdempotencyState",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "JiraIssueAction",
    "JiraIssueAdapter",
    "PagerDutyEventAction",
    "PagerDutyEventActionType",
    "PagerDutyEventsAdapter",
    "PagerDutySeverity",
    "RetryPolicy",
    "RetryingHttpExecutor",
    "SQLiteIdempotencyStore",
    "SlackAdapter",
    "SlackMessageAction",
    "SlackMode",
    "TransportConnectionFailure",
    "TransportFailure",
    "TransportTimeoutFailure",
]
