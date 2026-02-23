"""Prompt assembly for natural-language input in the interactive TUI."""

from __future__ import annotations

import os
import re
from pathlib import Path

from deeprepo.codebase_loader import ALL_EXTENSIONS, MAX_FILE_SIZE, SKIP_DIRS


STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "can",
    "shall",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "out",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "because",
    "but",
    "and",
    "or",
    "if",
    "while",
    "that",
    "this",
    "it",
    "its",
    "my",
    "your",
    "his",
    "her",
    "our",
    "their",
    "what",
    "which",
    "who",
    "whom",
    "these",
    "those",
    "i",
    "me",
    "we",
    "us",
    "you",
    "he",
    "she",
    "they",
    "them",
    "fix",
    "add",
    "update",
    "change",
    "modify",
    "implement",
    "create",
    "make",
    "get",
    "set",
}

SUPPORTED_EXTENSIONS = {ext.lower() for ext in ALL_EXTENSIONS}

LANG_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".zsh": "zsh",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".toml": "toml",
}


class PromptBuilder:
    def __init__(self, project_path: str, token_budget: int = 30000):
        self.project_path = str(Path(project_path).resolve())
        self.token_budget = token_budget
        self._cold_start: str | None = None

    def build(self, user_input: str) -> dict:
        """Assemble prompt, copy to clipboard, and return summary metadata."""
        try:
            cold_start = self._load_cold_start()
        except FileNotFoundError:
            return {
                "status": "error",
                "message": "Run /init first to generate project context",
                "data": {},
            }

        files = self._find_relevant_files(user_input)
        prompt = self._assemble_prompt(cold_start, files, user_input)
        token_estimate = self._estimate_tokens(prompt)
        copied = self._copy_to_clipboard(prompt)

        if copied:
            message = (
                f"Copied prompt ({token_estimate:,} tokens, "
                f"{len(files)} files) to clipboard"
            )
        else:
            message = (
                f"Built prompt ({token_estimate:,} tokens, {len(files)} files); "
                "clipboard unavailable"
            )

        return {
            "status": "success",
            "message": message,
            "data": {
                "prompt": prompt,
                "token_estimate": token_estimate,
                "files_included": [path for path, _ in files],
                "copied": copied,
            },
        }

    def _load_cold_start(self) -> str:
        """Read COLD_START.md, cache for the current shell session."""
        if self._cold_start is not None:
            return self._cold_start

        cold_start_path = Path(self.project_path) / ".deeprepo" / "COLD_START.md"
        if not cold_start_path.is_file():
            raise FileNotFoundError(str(cold_start_path))

        self._cold_start = cold_start_path.read_text(encoding="utf-8", errors="replace")
        return self._cold_start

    def _find_relevant_files(self, user_input: str) -> list[tuple[str, str]]:
        """Return list of (path, content) selected by keyword relevance."""
        keywords = self._extract_keywords(user_input)
        if not keywords:
            return []

        project_root = Path(self.project_path)
        skip_dirs = set(SKIP_DIRS) | {".deeprepo"}
        candidates: list[tuple[int, int, str, Path]] = []

        for dirpath, dirnames, filenames in os.walk(project_root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]

            for filename in filenames:
                file_path = Path(dirpath) / filename
                if not self._is_supported_file(file_path):
                    continue

                try:
                    file_size = file_path.stat().st_size
                except OSError:
                    continue

                if file_size > MAX_FILE_SIZE:
                    continue

                rel_path = file_path.relative_to(project_root).as_posix()
                score = self._score_file(rel_path, keywords)
                if score <= 0:
                    continue

                candidates.append((score, file_size, rel_path, file_path))

        if not candidates:
            return []

        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

        cold_tokens = self._estimate_tokens(self._cold_start or "")
        file_budget = max(self.token_budget - cold_tokens - 500, 0)
        used_tokens = 0
        selected: list[tuple[str, str]] = []

        for _, _, rel_path, file_path in candidates:
            if file_budget <= 0:
                break

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            file_tokens = self._estimate_tokens(content)
            if used_tokens + file_tokens > file_budget:
                continue

            selected.append((rel_path, content))
            used_tokens += file_tokens

        return selected

    def _assemble_prompt(
        self,
        cold_start: str,
        files: list[tuple[str, str]],
        user_ask: str,
    ) -> str:
        """Combine project context, relevant files, and user task into one prompt."""
        parts = ["# Project Context", cold_start.strip()]

        if files:
            parts.append("")
            parts.append("# Relevant Files")
            for rel_path, content in files:
                parts.append(f"## {rel_path}")
                parts.append(f"```{self._language_for_file(rel_path)}")
                parts.append(content.rstrip())
                parts.append("```")
                parts.append("")

        parts.append("# Your Task")
        parts.append(user_ask.strip())
        return "\n".join(parts).rstrip() + "\n"

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate using the char/4 heuristic."""
        if not text:
            return 0
        return max(1, int(len(text) / 4))

    # Backward-compatible alias for spec typo.
    def _estimate_tons(self, text: str) -> int:
        return self._estimate_tokens(text)

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard; return False if clipboard access fails."""
        try:
            import pyperclip

            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def _extract_keywords(self, user_input: str) -> list[str]:
        words = re.findall(r"[a-z0-9_]+", user_input.lower())
        return [w for w in words if len(w) >= 2 and w not in STOPWORDS]

    def _score_file(self, rel_path: str, keywords: list[str]) -> int:
        rel = Path(rel_path)
        basename = rel.name.lower()
        parent_parts = [p.lower() for p in rel.parent.parts if p and p != "."]
        score = 0

        for keyword in keywords:
            if keyword in basename:
                score += 3
            if any(keyword in part for part in parent_parts):
                score += 1

        return score

    def _is_supported_file(self, file_path: Path) -> bool:
        name_lower = file_path.name.lower()
        ext_lower = file_path.suffix.lower()

        if ext_lower in SUPPORTED_EXTENSIONS:
            return True

        # Handles dotfiles like ".env" where Path.suffix is empty.
        return any(name_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS)

    def _language_for_file(self, rel_path: str) -> str:
        ext = Path(rel_path).suffix.lower()
        return LANG_BY_EXTENSION.get(ext, ext.lstrip(".") or "text")
