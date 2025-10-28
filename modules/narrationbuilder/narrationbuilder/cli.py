from __future__ import annotations

import sys
import os
import pathlib

# Ensure package import works when running this file directly
if __package__ is None or __package__ == "":
    # append parent of package directory to sys.path (…/modules/narrationbuilder)
    sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

import typer
from narrationbuilder.run import run_narration
from narrationbuilder.logging_utils import emit_evt

app = typer.Typer(add_completion=False)


@app.command()
def main(
    project_root: str = typer.Option(..., "--project-root", help="Path to project root (parent of outputs/)"),
    topic_id: str = typer.Option(..., "--topic-id", help="Slug topic ID, e.g. vznik-ceskoslovenska"),
    episode_id: str = typer.Option(..., "--episode-id", help="Two-digit episode id, e.g. 01"),
    lang: str = typer.Option(..., "--lang", help="Language code: CS/EN/DE/ES/FR"),
    model: str = typer.Option("gpt-5", "--model", help="OpenAI model, default gpt-5; fallback gpt-4.1"),
    style: str = typer.Option("historicko-dokumentární, klidné tempo, čitelné i pro laika", "--style"),
    length_words: str = typer.Option("1800-2200", "--length-words"),
    sentence_len: str = typer.Option("20-30 slov", "--sentence-len"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build prompt_pack only; no LLM call"),
):
    try:
        # Ensure env defaults for temperature from .env are respected if present
        os.environ.setdefault("GPT_TEMPERATURE", "0.4")
        emit_evt({"type": "phase", "value": "start"})
        code = run_narration(
            project_root=project_root,
            topic_id=topic_id,
            episode_id=episode_id,
            lang=lang.upper(),
            model=model,
            style=style,
            length_words=length_words,
            sentence_len=sentence_len,
            dry_run=dry_run,
        )
        raise typer.Exit(code)
    except typer.Exit as e:
        raise e
    except Exception as e:
        emit_evt({"type": "error", "code": "unhandled", "message": str(e)})
        raise typer.Exit(5)


if __name__ == "__main__":
    app()
