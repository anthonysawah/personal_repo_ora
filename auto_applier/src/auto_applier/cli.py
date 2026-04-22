from __future__ import annotations

import json as _json
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import select

from . import config as _config
from .db import init_db, session_scope
from .models import Application, AppStatus, Job
from .pipeline import run_daily, run_discover, run_score, run_tailor
from .profile.scaffold import scaffold as scaffold_profile
from .submit.runner import run_submit
from .utils.logging import setup_logging

app = typer.Typer(add_completion=False, no_args_is_help=True, help="auto_applier — tailored job submissions at scale")
console = Console()


@app.callback()
def _root() -> None:
    setup_logging()


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing profile.yaml / base_resume.md."),
) -> None:
    """Scaffold data/profile.yaml + data/base_resume.md + data/companies.yaml."""
    _config.settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()

    env_example = Path(__file__).parent.parent.parent / ".env.example"
    env_dest = Path(".env")
    if env_example.exists() and not env_dest.exists():
        shutil.copy(env_example, env_dest)
        console.print(f"[green]✓[/green] Wrote .env (copy of .env.example). Fill in ANTHROPIC_API_KEY.")

    written = scaffold_profile(_config.settings.data_dir, force=force)
    if not written:
        console.print("[yellow]All scaffold files already exist. Use --force to overwrite.[/yellow]")
    for p in written:
        console.print(f"[green]✓[/green] wrote {p}")
    console.print(
        "\nNext: fill in [cyan]data/profile.yaml[/cyan] and [cyan]data/base_resume.md[/cyan], "
        "then run [cyan]auto_applier doctor[/cyan]."
    )


@app.command()
def doctor() -> None:
    """Validate environment, DB, profile, and Anthropic connectivity."""
    ok = True

    if not _config.settings.anthropic_api_key:
        console.print("[red]✗[/red] ANTHROPIC_API_KEY is not set (check .env)")
        ok = False
    else:
        console.print("[green]✓[/green] ANTHROPIC_API_KEY set")

    for p, label in [
        (_config.settings.profile_path, "profile.yaml"),
        (_config.settings.base_resume_path, "base_resume.md"),
        (_config.settings.companies_path, "companies.yaml"),
    ]:
        if p.exists():
            console.print(f"[green]✓[/green] {label} at {p}")
        else:
            console.print(f"[red]✗[/red] {label} missing at {p}  — run `auto_applier init`")
            ok = False

    try:
        init_db()
        console.print(f"[green]✓[/green] DB reachable at {_config.settings.db_url}")
    except Exception as e:
        console.print(f"[red]✗[/red] DB error: {e}")
        ok = False

    if _config.settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=_config.settings.anthropic_api_key)
            resp = client.messages.create(
                model=_config.settings.score_model,
                max_tokens=20,
                messages=[{"role": "user", "content": "Say 'ok' (2 chars)."}],
            )
            text = next((b.text for b in resp.content if b.type == "text"), "")
            console.print(f"[green]✓[/green] Anthropic API reachable (model={_config.settings.score_model}): {text.strip()}")
        except Exception as e:
            console.print(f"[red]✗[/red] Anthropic API call failed: {e}")
            ok = False

    raise typer.Exit(0 if ok else 1)


@app.command()
def discover(
    source: list[str] = typer.Option(["greenhouse"], "--source", help="One or more of: greenhouse, lever, ashby, rss"),
) -> None:
    """Fetch jobs from configured discovery adapters."""
    init_db()
    stats = run_discover(source)
    console.print_json(data=stats)


@app.command()
def score(
    threshold: int = typer.Option(30, "--threshold", help="Prefilter threshold 0-100."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Prefilter only, skip Claude scoring."),
) -> None:
    """Score discovered jobs against profile."""
    init_db()
    stats = run_score(prefilter_threshold=threshold, llm=not no_llm)
    console.print_json(data=stats)


@app.command()
def tailor(
    limit: Optional[int] = typer.Option(None, "--limit", help="Max tailorings this run."),
    min_score: int = typer.Option(60, "--min-score", help="Minimum fit_score to tailor."),
) -> None:
    """Tailor resumes for top-scored applications, ready for approval."""
    init_db()
    stats = run_tailor(limit=limit, min_score=min_score)
    console.print_json(data=stats)


@app.command(name="run-daily")
def run_daily_cmd(
    source: list[str] = typer.Option(["greenhouse"], "--source"),
    tailor_limit: Optional[int] = typer.Option(None, "--tailor-limit"),
) -> None:
    """Full pipeline: discover → score → tailor."""
    init_db()
    stats = run_daily(source, tailor_limit=tailor_limit)
    console.print_json(data=stats)


@app.command()
def review(
    host: Optional[str] = typer.Option(None, "--host"),
    port: Optional[int] = typer.Option(None, "--port"),
) -> None:
    """Open the FastAPI approval dashboard."""
    from .approval.app import serve

    init_db()
    serve(host=host, port=port)


@app.command()
def submit(
    dry_run: bool = typer.Option(False, "--dry-run", help="Log submissions without hitting network."),
    limit: Optional[int] = typer.Option(None, "--limit"),
) -> None:
    """Submit all approved applications via the matched ATS adapter."""
    init_db()
    stats = run_submit(dry_run=dry_run, limit=limit)
    console.print_json(data=stats)


@app.command()
def status(
    today: bool = typer.Option(False, "--today", help="Show today's activity only."),
) -> None:
    """Print a summary of jobs + applications in the DB."""
    init_db()
    with session_scope() as session:
        jobs = session.exec(select(Job)).all()
        apps = session.exec(select(Application)).all()

    t = Table(title="auto_applier status")
    t.add_column("Kind")
    t.add_column("Count", justify="right")
    t.add_row("Jobs discovered", str(len(jobs)))
    for s in AppStatus:
        t.add_row(f"Apps · {s.value}", str(sum(1 for a in apps if a.status == s)))
    console.print(t)


@app.command(name="export-profile-schema")
def export_schema() -> None:
    """Dump the Profile JSON schema (for debugging tailor prompts)."""
    from .profile.schema import Profile

    console.print_json(_json.dumps(Profile.model_json_schema()))


if __name__ == "__main__":
    app()
