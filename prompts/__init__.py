"""
Prompt loader — reads .txt prompt files relative to this package directory.

Usage:
    from prompts import load_prompt
    text = load_prompt("planner")          # loads prompts/planner.txt
    text = load_prompt("planner", tools_schema="...")  # fills {tools_schema}
"""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: str) -> str:
    """
    Load a prompt file by name (without extension) and optionally
    format it with keyword arguments.

    Parameters
    ----------
    name : str
        Filename without extension, e.g. "planner" or "synthesizer".
    **kwargs : str
        Optional format values to substitute into the prompt text.
        Uses str.format_map so only named placeholders are replaced;
        curly braces that are not placeholders must be doubled ({{ }}).

    Returns
    -------
    str
        The prompt text, optionally formatted.

    Raises
    ------
    FileNotFoundError
        If the prompt file does not exist.
    """
    path = _DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if kwargs:
        text = text.format_map(kwargs)
    return text