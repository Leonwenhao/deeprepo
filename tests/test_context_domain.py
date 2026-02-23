"""Tests for the context domain configuration."""

from deeprepo.domains import DOMAIN_REGISTRY, get_domain


def test_context_domain_registered():
    """Context domain is in the registry."""
    assert "context" in DOMAIN_REGISTRY


def test_context_domain_get():
    """get_domain('context') returns a valid DomainConfig."""
    domain = get_domain("context")
    assert domain.name == "context"
    assert domain.label == "Project Context Generation"


def test_context_domain_data_variable():
    """Context domain uses 'codebase' variable (same as code domain)."""
    domain = get_domain("context")
    assert domain.data_variable_name == "codebase"


def test_context_root_prompt_has_required_sections():
    """Root prompt instructs for the 6-section output structure."""
    domain = get_domain("context")
    prompt = domain.root_system_prompt
    for section in [
        "Identity",
        "Architecture",
        "Module Map",
        "Patterns",
        "Dependency Graph",
        "Tech Debt",
    ]:
        assert section in prompt, f"Missing section '{section}' in root prompt"


def test_context_root_prompt_has_repl_instructions():
    """Root prompt includes REPL mechanics (same engine as code domain)."""
    domain = get_domain("context")
    prompt = domain.root_system_prompt
    assert "codebase" in prompt
    assert "llm_batch" in prompt
    assert "set_answer" in prompt
    assert "execute_python" in prompt


def test_context_sub_prompt_focuses_on_documentation():
    """Sub prompt asks for module documentation, not bug hunting."""
    domain = get_domain("context")
    prompt = domain.sub_system_prompt
    assert "Purpose" in prompt
    assert "Entry point" in prompt or "entry point" in prompt
    assert "Conventions" in prompt or "conventions" in prompt


def test_context_user_prompt_has_placeholders():
    """User prompt template has {metadata_str} and {file_tree} placeholders."""
    domain = get_domain("context")
    assert "{metadata_str}" in domain.user_prompt_template
    assert "{file_tree}" in domain.user_prompt_template


def test_context_user_prompt_stack_and_batch_instructions():
    """User prompt tells model to inspect stack config files and use llm_batch()."""
    domain = get_domain("context")
    prompt = domain.user_prompt_template
    assert "pyproject.toml" in prompt
    assert "package.json" in prompt
    assert "Cargo.toml" in prompt
    assert "llm_batch()" in prompt


def test_context_baseline_prompt_exists():
    """Baseline prompt exists and mentions documentation."""
    domain = get_domain("context")
    assert len(domain.baseline_system_prompt) > 100
    assert "Identity" in domain.baseline_system_prompt or "identity" in domain.baseline_system_prompt


def test_context_domain_has_clone_handler():
    """Context domain supports git URLs via clone_handler."""
    domain = get_domain("context")
    assert domain.clone_handler is not None
