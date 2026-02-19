"""Code analysis domain configuration."""

from ..codebase_loader import load_codebase, format_metadata_for_prompt, clone_repo
from ..prompts import ROOT_SYSTEM_PROMPT, SUB_SYSTEM_PROMPT, ROOT_USER_PROMPT_TEMPLATE
from ..baseline import BASELINE_SYSTEM_PROMPT
from .base import DomainConfig

CODE_DOMAIN = DomainConfig(
    name="code",
    label="Codebase Analysis",
    description="Analyze source code repositories for architecture, bugs, and quality",
    loader=load_codebase,
    format_metadata=format_metadata_for_prompt,
    root_system_prompt=ROOT_SYSTEM_PROMPT,
    sub_system_prompt=SUB_SYSTEM_PROMPT,
    user_prompt_template=ROOT_USER_PROMPT_TEMPLATE,
    baseline_system_prompt=BASELINE_SYSTEM_PROMPT,
    data_variable_name="codebase",
    clone_handler=clone_repo,
)
