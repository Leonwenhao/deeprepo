"""
Integration tests for the film domain.
Verifies: loader -> domain config -> namespace -> prompt rendering.
No API calls required.
"""

import pytest


def test_film_domain_loads_and_configures():
    """Verify FILM_DOMAIN config is complete and consistent."""
    from deeprepo.domains import get_domain
    domain = get_domain("film")
    assert domain.name == "film"
    assert domain.data_variable_name == "scenes"
    assert domain.clone_handler is None
    assert callable(domain.loader)
    assert callable(domain.format_metadata)
    assert len(domain.root_system_prompt) > 500
    assert len(domain.sub_system_prompt) > 200
    assert len(domain.baseline_system_prompt) > 100


def test_film_loader_output_matches_engine_contract():
    """Verify loader output has the keys the engine expects."""
    from deeprepo.film_loader import load_screenplay
    data = load_screenplay("tests/test_screenplay.txt")

    # Engine does: data[domain.data_variable_name]
    # For film, that's data["scenes"]
    assert "scenes" in data
    assert "file_tree" in data
    assert "metadata" in data

    scenes = data["scenes"]
    assert isinstance(scenes, dict)
    assert len(scenes) >= 3

    for key, value in scenes.items():
        assert isinstance(key, str)
        assert isinstance(value, str)
        assert key.startswith("SC-")


def test_film_metadata_has_required_fields():
    """Verify metadata dict has all fields the prompts reference."""
    from deeprepo.film_loader import load_screenplay
    data = load_screenplay("tests/test_screenplay.txt")
    meta = data["metadata"]

    required_fields = [
        "title", "source_file", "total_scenes", "total_pages_est",
        "total_chars", "total_words", "characters", "total_characters",
        "scene_headers", "int_ext_breakdown", "time_of_day_breakdown",
        "avg_scene_length_chars", "longest_scenes",
    ]
    for field in required_fields:
        assert field in meta, f"Missing metadata field: {field}"


def test_film_metadata_formatting():
    """Verify format_film_metadata produces a usable prompt string."""
    from deeprepo.film_loader import load_screenplay, format_film_metadata
    data = load_screenplay("tests/test_screenplay.txt")
    meta_str = format_film_metadata(data["metadata"])
    assert isinstance(meta_str, str)
    assert len(meta_str) > 100
    assert "scene" in meta_str.lower()


def test_film_user_prompt_template_renders():
    """Verify user prompt template renders with real loader output."""
    from deeprepo.domains import get_domain
    from deeprepo.film_loader import load_screenplay, format_film_metadata

    domain = get_domain("film")
    data = load_screenplay("tests/test_screenplay.txt")
    meta_str = format_film_metadata(data["metadata"])

    prompt = domain.user_prompt_template.format(
        metadata_str=meta_str,
        file_tree=data["file_tree"],
        total_scenes=data["metadata"]["total_scenes"],
        total_characters=data["metadata"]["total_characters"],
    )
    assert len(prompt) > 200
    assert "scene" in prompt.lower()
    assert "5" in prompt  # 5 scenes from test fixture


def test_film_domain_registry_consistent():
    """Verify film is properly registered alongside code and content."""
    from deeprepo.domains import DOMAIN_REGISTRY, get_domain
    assert "film" in DOMAIN_REGISTRY
    assert "code" in DOMAIN_REGISTRY
    assert "content" in DOMAIN_REGISTRY
    domain = get_domain("film")
    assert domain is DOMAIN_REGISTRY["film"]
