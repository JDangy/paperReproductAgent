from __future__ import annotations

"""Slash command completion engine."""

from dataclasses import dataclass, field
import re

from .commands import COMMANDS


@dataclass
class CompletionItem:
    command: str
    args: str
    description: str
    category: str
    score: int = 0

    @property
    def display_text(self) -> str:
        arg_part = f" {self.args}" if self.args else ""
        return f"/{self.command}{arg_part}  [{self.category}] {self.description}"

    @property
    def insert_text(self) -> str:
        return f"/{self.command}"


def normalize_query(text: str) -> str:
    """Remove /, -, _, spaces; lowercase."""
    return re.sub(r"[/\-_\s]", "", text).lower()


def _candidate_strings(meta) -> list[str]:
    """All searchable strings for a command."""
    return [
        meta.name,
        f"/{meta.name}",
        meta.args or "",
        meta.description,
        meta.category,
    ]


def fuzzy_subsequence_score(query: str, candidate: str) -> int | None:
    """Return gap-penalty score for subsequence match, or None if no match.

    Lower score = better match.  Each character match costs 0, each gap costs 1.
    """
    q = normalize_query(query)
    c = normalize_query(candidate)
    if not q:
        return 0
    qi = 0
    score = 0
    for ci, ch in enumerate(c):
        if qi >= len(q):
            break
        if ch == q[qi]:
            qi += 1
        else:
            score += 1
    if qi < len(q):
        return None
    return score


def complete_command(prefix: str, limit: int = 8) -> list[CompletionItem]:
    """Return sorted completion candidates for a slash-command prefix.

    Returns empty list if *prefix* does not start with ``/``.
    """
    if not prefix.startswith("/"):
        return []

    query = prefix[1:]  # strip leading /
    q_norm = normalize_query(query)

    # When query is empty (just "/"), return all commands
    effective_limit = max(limit, len(COMMANDS)) if not query else limit

    items: list[CompletionItem] = []

    for name, meta in COMMANDS.items():
        if name == "exit" and query and query.lower() not in ("e", "ex", "exi", "exit"):
            # hide "exit" unless user explicitly types /e or /exit
            continue

        score = _score_command(query, q_norm, meta)
        if score is not None:
            items.append(CompletionItem(
                command=meta.name,
                args=meta.args,
                description=meta.description,
                category=meta.category,
                score=score,
            ))

    # Deduplicate by command name, keeping best (lowest) score
    seen: dict[str, CompletionItem] = {}
    for item in items:
        if item.command not in seen or item.score < seen[item.command].score:
            seen[item.command] = item

    result = sorted(seen.values(), key=lambda x: x.score)
    return result[:effective_limit]


def _score_command(query: str, q_norm: str, meta) -> int | None:
    """Score how well a command matches a query.  Lower is better.

    Returns None if there is no match at all.
    """
    name = meta.name
    name_norm = normalize_query(name)

    # Exact match on command name
    if query.lower() == name.lower():
        return 0

    # Prefix match on command name
    if name.lower().startswith(query.lower()):
        return 1

    # Prefix match on normalized name
    if name_norm.startswith(q_norm):
        return 2

    # Word-prefix match on any candidate string
    for s in _candidate_strings(meta):
        for word in s.split():
            if word.lower().startswith(query.lower()):
                return 3
            if normalize_query(word).startswith(q_norm):
                return 4

    # Fuzzy subsequence match on command name first (preferred)
    fuzzy_score = fuzzy_subsequence_score(query, name)
    if fuzzy_score is not None:
        return 10 + fuzzy_score

    # Fuzzy on full candidate strings
    for s in _candidate_strings(meta):
        fs = fuzzy_subsequence_score(query, s)
        if fs is not None:
            return 20 + fs

    # Fuzzy on query normalized vs candidate normalized
    for s in _candidate_strings(meta):
        if q_norm:  # only if there's meaningful query after normalization
            fs = fuzzy_subsequence_score(q_norm, normalize_query(s))
            if fs is not None:
                return 30 + fs

    return None
