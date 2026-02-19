from dataclasses import dataclass
from typing import Callable


@dataclass
class DomainConfig:
    """Configuration for a deeprepo analysis domain."""

    # Identity
    name: str  # e.g., "code", "content"
    label: str  # e.g., "Codebase Analysis"
    description: str  # One-line description for CLI help

    # Loader
    loader: Callable[[str], dict]  # path -> {<data_variable_name>: dict, file_tree: str, metadata: dict}
    format_metadata: Callable[[dict], str]  # metadata dict -> prompt string

    # Prompts
    root_system_prompt: str  # System prompt for root orchestrator
    sub_system_prompt: str  # System prompt for sub-LLM workers
    user_prompt_template: str  # Initial user message (with {metadata_str}, {file_tree})
    baseline_system_prompt: str  # System prompt for single-model baseline

    # Namespace
    data_variable_name: str = "documents"  # Key in loader return dict AND namespace variable name

    # File handling
    clone_handler: Callable[[str], str] | None = None  # Optional: handle URLs (git clone, etc.)
