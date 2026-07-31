"""Command-line interface for LedgerLens.

The CLI deliberately loads runtime adapters and optional web dependencies only when a
command needs them.  This keeps validation and fixture tests deterministic while the
DataHub integration is developed independently.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import webbrowser
from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from pathlib import Path
from threading import Timer
from typing import Annotated, Any

import typer

app = typer.Typer(
    name="ledgerlens",
    help="Evidence-grounded failure-ledger triage through DataHub.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

AdapterFactory = Callable[..., Any]
_adapter_factory: AdapterFactory | None = None

_SECRET_KEY = re.compile(
    r"(authorization|cookie|password|secret|token|api[_-]?key|credential)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT_SECRET = re.compile(r"(?i)\b(token|password|secret|api[_-]?key)=([^&\s]+)")


class OutputFormat(StrEnum):
    """Supported machine- and human-readable output formats."""

    json = "json"
    markdown = "markdown"


def set_adapter_factory(factory: AdapterFactory | None) -> None:
    """Inject an adapter factory.

    This hook is intentionally tiny: tests and the core integration can provide an
    object implementing the command methods without importing DataHub at CLI import
    time.
    """

    global _adapter_factory
    _adapter_factory = factory


def _safe_text(value: object) -> str:
    text = str(value)
    text = _BEARER.sub(r"\1[REDACTED]", text)
    return _ASSIGNMENT_SECRET.sub(r"\1=[REDACTED]", text)


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_plain(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_plain(model_dump(mode="json"))
    if hasattr(value, "__dict__"):
        return _to_plain(vars(value))
    return _safe_text(value)


def _redact(value: Any) -> Any:
    plain = _to_plain(value)
    if isinstance(plain, dict):
        return {
            key: "[REDACTED]" if _SECRET_KEY.search(key) else _redact(item)
            for key, item in plain.items()
        }
    if isinstance(plain, list):
        return [_redact(item) for item in plain]
    if isinstance(plain, str):
        return _safe_text(plain)
    return plain


async def _await_result(value: Awaitable[Any]) -> Any:
    return await value


def _run_awaitable(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_await_result(value))
    raise RuntimeError("Async adapter calls cannot run inside an active event loop.")


def _invoke(adapter: Any, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    function = getattr(adapter, method, None)
    if not callable(function):
        raise RuntimeError(f"The configured adapter does not implement '{method}'.")
    result = _run_awaitable(function(*args, **kwargs))
    plain = _redact(result)
    if not isinstance(plain, dict):
        return {"result": plain}
    return plain


def _resolve_adapter(demo: bool) -> Any:
    # ledgerlens.web is safe to import without FastAPI installed; create_app performs
    # the optional import only for serve/demo.
    from ledgerlens.web import resolve_adapter

    return resolve_adapter(demo=demo, factory=_adapter_factory)


def _markdown(payload: Mapping[str, Any], title: str) -> str:
    from ledgerlens.web import render_markdown_report

    return render_markdown_report(payload, title=title)


def _emit(
    payload: Mapping[str, Any],
    *,
    output_format: OutputFormat,
    title: str,
    output: Path | None = None,
) -> None:
    clean = _redact(payload)
    if output_format is OutputFormat.markdown:
        rendered = _markdown(clean, title)
    else:
        rendered = json.dumps(clean, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if output is None:
        typer.echo(rendered, nl=False)
        return

    if output.exists():
        raise RuntimeError(f"Refusing to overwrite existing report: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    typer.echo(f"Wrote {output}")


def _fail(exc: Exception, *, code: int = 2) -> None:
    typer.echo(f"Error: {_safe_text(exc)}", err=True)
    raise typer.Exit(code=code)


def _check_source(source: Path | None, *, required: bool) -> Path | None:
    if source is None:
        if required:
            raise RuntimeError(
                "A source path is required outside explicit demo mode; pass --demo "
                "to use the deterministic fixture."
            )
        return None
    if not source.exists():
        raise RuntimeError(f"Source path does not exist: {source}")
    if not source.is_file():
        raise RuntimeError(f"Source path is not a file: {source}")
    return source


@app.command()
def validate(
    source: Annotated[
        Path | None,
        typer.Argument(help="Failure-ledger file to validate. Omit only with --demo."),
    ] = None,
    demo: Annotated[
        bool,
        typer.Option(
            "--demo",
            help="Validate the deterministic fixture; no live DataHub request is made.",
        ),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.json,
) -> None:
    """Validate a ledger without ingesting or mutating DataHub."""

    try:
        checked_source = _check_source(source, required=not demo)
        payload = _invoke(_resolve_adapter(demo), "validate", checked_source)
        _emit(payload, output_format=output_format, title="LedgerLens validation")
    except Exception as exc:
        _fail(exc)


@app.command()
def ingest(
    source: Annotated[
        Path | None,
        typer.Argument(help="Failure-ledger file to ingest. Omit only with --demo."),
    ] = None,
    demo: Annotated[
        bool,
        typer.Option(
            "--demo",
            help="Exercise the deterministic fixture without mutating DataHub.",
        ),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.json,
) -> None:
    """Ingest a validated ledger through the configured adapter."""

    try:
        checked_source = _check_source(source, required=not demo)
        payload = _invoke(_resolve_adapter(demo), "ingest", checked_source)
        _emit(payload, output_format=output_format, title="LedgerLens ingestion")
    except Exception as exc:
        _fail(exc)


@app.command()
def explain(
    finding_id: Annotated[str, typer.Argument(help="Stable finding identifier.")],
    demo: Annotated[
        bool,
        typer.Option(
            "--demo",
            help="Use the deterministic fixture; no live DataHub request is made.",
        ),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.markdown,
) -> None:
    """Explain one finding with ownership, evidence, and audit context."""

    try:
        payload = _invoke(_resolve_adapter(demo), "explain", finding_id)
        _emit(payload, output_format=output_format, title=f"Finding: {finding_id}")
    except Exception as exc:
        _fail(exc)


@app.command()
def supersession(
    finding_id: Annotated[
        str,
        typer.Argument(help="Finding whose supersession chain to trace."),
    ],
    demo: Annotated[
        bool,
        typer.Option(
            "--demo",
            help="Use the deterministic fixture; no live DataHub request is made.",
        ),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.markdown,
) -> None:
    """Trace a finding's supersession chain without discarding history."""

    try:
        payload = _invoke(_resolve_adapter(demo), "supersession", finding_id)
        _emit(payload, output_format=output_format, title=f"Supersession: {finding_id}")
    except Exception as exc:
        _fail(exc)


@app.command()
def triage(
    demo: Annotated[
        bool,
        typer.Option(
            "--demo",
            help="Use the deterministic fixture; no live DataHub request is made.",
        ),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.markdown,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write a new report file instead of stdout; existing files are not overwritten.",
        ),
    ] = None,
) -> None:
    """Generate a deterministic remediation queue."""

    try:
        payload = _invoke(_resolve_adapter(demo), "triage")
        _emit(
            payload,
            output_format=output_format,
            title="LedgerLens remediation queue",
            output=output,
        )
    except Exception as exc:
        _fail(exc)


def _run_server(
    *,
    host: str,
    port: int,
    demo_mode: bool,
    open_browser: bool,
    incident_fixture_mode: bool | None = None,
    incident_autonomous_execution: bool | None = None,
    incident_only: bool = False,
) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("The web extra is required. Install LedgerLens with '[web]'.") from exc

    from ledgerlens.web import create_app

    try:
        adapter = _resolve_adapter(demo_mode)
    except Exception:
        if not incident_only:
            raise
        from ledgerlens.web import UnavailableDataAdapter

        adapter = UnavailableDataAdapter(
            "Legacy findings adapter is not configured; Incident Commander is primary."
        )
    application = create_app(
        adapter=adapter,
        demo_mode=demo_mode,
        incident_fixture_mode=incident_fixture_mode,
        incident_autonomous_execution=incident_autonomous_execution,
    )
    if open_browser:
        Timer(0.8, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(application, host=host, port=port, log_level="info")


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535, help="TCP port.")] = 8000,
    demo: Annotated[
        bool,
        typer.Option("--demo", help="Serve the visibly labeled deterministic fixture."),
    ] = False,
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open-browser",
            help="Open the local URL after the server starts.",
        ),
    ] = False,
) -> None:
    """Serve the web interface with a live adapter or explicit fixture mode."""

    try:
        _run_server(host=host, port=port, demo_mode=demo, open_browser=open_browser)
    except Exception as exc:
        _fail(exc)


@app.command()
def demo(
    host: Annotated[str, typer.Option(help="Interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535, help="TCP port.")] = 8000,
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open-browser/--no-open-browser",
            help="Open the local demo URL after the server starts.",
        ),
    ] = True,
) -> None:
    """Launch the contest-ready UI using clearly labeled fixture data."""

    typer.echo("Starting LedgerLens in DEMO FIXTURE mode; DataHub will not be contacted.")
    try:
        _run_server(host=host, port=port, demo_mode=True, open_browser=open_browser)
    except Exception as exc:
        _fail(exc)


@app.command("incident-commander")
def incident_commander(
    host: Annotated[str, typer.Option(help="Interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535, help="TCP port.")] = 8000,
    fixture: Annotated[
        bool,
        typer.Option(
            "--fixture/--live",
            help="Use the deterministic replay or require injected live integrations.",
        ),
    ] = True,
    autonomous: Annotated[
        bool,
        typer.Option(
            "--autonomous/--manual",
            help="Run verifier-quorum plus deterministic authorization automatically.",
        ),
    ] = False,
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open-browser/--no-open-browser",
            help="Open the Incident Commander URL after the server starts.",
        ),
    ] = True,
) -> None:
    """Launch the Autonomous Data Incident Commander."""

    mode = "FIXTURE / REPLAY" if fixture else "LIVE"
    automation = "autonomous verifier-gated" if autonomous else "manual authorization"
    typer.echo(f"Starting LedgerLens Incident Commander in {mode} mode ({automation}).")
    if open_browser:
        Timer(0.8, lambda: webbrowser.open(f"http://{host}:{port}/incident")).start()
    try:
        _run_server(
            host=host,
            port=port,
            demo_mode=fixture,
            open_browser=False,
            incident_fixture_mode=fixture,
            incident_autonomous_execution=autonomous,
            incident_only=True,
        )
    except Exception as exc:
        _fail(exc)


if __name__ == "__main__":
    app()
