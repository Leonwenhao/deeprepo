from .base import DomainConfig
from .code import CODE_DOMAIN
from .content import CONTENT_DOMAIN

DOMAIN_REGISTRY: dict[str, DomainConfig] = {
    "code": CODE_DOMAIN,
    "content": CONTENT_DOMAIN,
}

DEFAULT_DOMAIN = "code"


def get_domain(name: str) -> DomainConfig:
    """Look up a domain config by name."""
    if name not in DOMAIN_REGISTRY:
        available = ", ".join(DOMAIN_REGISTRY.keys())
        raise ValueError(f"Unknown domain '{name}'. Available: {available}")
    return DOMAIN_REGISTRY[name]
