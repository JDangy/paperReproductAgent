from __future__ import annotations

import re

def clean_display_text(text: str) -> str:
    """Clean Markdown/Rich artifacts for terminal plain display."""
    if not text or not isinstance(text, str):
        return ""
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(
        r"\[/?(?:bold|dim|italic|underline|reverse|blink|#[0-9a-fA-F]{6}|[a-zA-Z_ -]+)(?: [^\]]+)?\]",
        "", text,
    )
    return text.strip()
