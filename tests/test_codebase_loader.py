"""Tests for codebase_loader — skip-directory filtering."""

import os
import tempfile

from deeprepo.codebase_loader import load_codebase


def test_deeprepo_dir_excluded_from_scan():
    """Files inside .deeprepo/ must not be loaded into the codebase."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a normal source file
        with open(os.path.join(tmpdir, "main.py"), "w") as f:
            f.write("print('hello')\n")

        # Create .deeprepo/ with a file that would normally match
        deeprepo_dir = os.path.join(tmpdir, ".deeprepo")
        os.makedirs(deeprepo_dir)
        with open(os.path.join(deeprepo_dir, "config.yaml"), "w") as f:
            f.write("version: 1\n")
        with open(os.path.join(deeprepo_dir, "internal.py"), "w") as f:
            f.write("# should be excluded\n")

        data = load_codebase(tmpdir)
        paths = set(data["codebase"].keys())

        assert "main.py" in paths
        assert not any(".deeprepo" in p for p in paths), (
            f".deeprepo/ files should be excluded, got: {paths}"
        )
