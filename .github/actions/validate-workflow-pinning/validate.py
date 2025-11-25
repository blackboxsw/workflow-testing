#!/usr/bin/env python3
"""
Validates that GitHub Actions in workflows are pinned to commit SHAs.

This script checks workflow files for 'uses:' statements and ensures they
reference actions by their full 40-character commit SHA rather than tags or
branches.
"""

import os
from pathlib import Path
import re
import sys
from typing import List, Tuple

try:
    from ruamel.yaml import YAML
except ImportError:
    print(
        "Error: ruamel.yaml is required. Install with: pip install ruamel.yaml",
        file=sys.stderr,
    )
    sys.exit(1)


SHA_PATTERN = re.compile(r".+@[a-f0-9]{40}$")


def get_uses_statements(file_path: str) -> List[Tuple[str, int]]:
    """
    Extract all 'uses:' statements from a workflow file with their line numbers.

    Uses ruamel.yaml to annotate line number information from the original file.

    Returns:
        List of tuples containing (uses_value, line_number)
    """
    uses_statements = []

    yaml = YAML()
    try:
        with open(file_path, "r") as f:
            content = yaml.load(f)
    except Exception as e:
        print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)

    # When YAML contains neither jobs nor runs it is an unsupported workflow.
    if not content or {"jobs", "runs"}.intersection(content.keys()) == set():
        return []

    # Obtain closest leaf YAML key data which may contain a list of steps.
    # Local action.yaml has 'runs' with optional nested steps whereas
    # workflows contain 'jobs' with nested job_ids with optional nested steps.
    step_operations = (
        [content["runs"]] if "runs" in content else content["jobs"].values()
    )
    for step_data in step_operations:
        for step in step_data.get("steps", []):
            uses_value = step.get("uses")
            if step.get("uses"):
                # Get 0-based line number from ruamel.yaml's line col info.
                line_num = 0  # 0 indicates an unknown line number
                if "uses" in step.lc.data:
                    # Convert index number to line number
                    line_num = step.lc.data["uses"][0] + 1
                uses_statements.append((uses_value, line_num))

    return uses_statements


def validate_workflow_files(
    changed_files: List[str], allow_unpinned: List[str], fail_on_error: bool
) -> int:
    """
    Validate workflow files for proper SHA pinning.

    Args:
        changed_files: List of file paths to check
        allow_unpinned: List of allowed unpinned action references
        fail_on_error: Whether to exit with error code on validation failure

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("Checking for 'uses:' statements without SHA pins...")

    fail = False
    if not changed_files:
        changed_files = [
            str(p)
            for p in Path(".github/workflows").rglob("*.yml")
        ] + [
            str(p)
            for p  in Path(".github/actions").rglob("*.yml")
        ]
        print(f"FILES TO LOOK AT {changed_files}")

    for file_path in changed_files:
        if ".github/workflows" not in file_path and ".github/actions" not in file_path:
            continue

        # Skip if file doesn't exist (e.g., deleted files).
        if not os.path.isfile(file_path):
            continue

        for uses_value, line_num in get_uses_statements(file_path):
            # Ignore local actions which have no pin.
            if os.path.isdir(uses_value):
                continue

            if SHA_PATTERN.match(uses_value):
                continue

            if uses_value in allow_unpinned:
                print(
                    f"[{file_path}:{line_num}] Ignoring allowed-unpinned: {uses_value}"
                )
                continue

            fail = True
            print(
                f"[{file_path}:{line_num}] ❌ ERROR: Not pinned using commit SHA: {uses_value}"
            )

    if fail:
        print("❌ Some workflows are using tags or branches instead of commit SHAs.")
        print(
            "Best practice: pin SHAs with comment for tag/branch <some_action>@<commit_SHA> # v<major>.<minor>.<patch>"
        )

        if fail_on_error:
            return 1
    else:
        print("✅ All 'uses:' statements are correctly pinned to SHAs.")

    return 0


def main():
    all_changed_files = os.environ.get("ALL_CHANGED_FILES", "")
    fail_on_error_str = os.environ.get("FAIL_ON_ERROR", "true")
    allow_unpinned_str = os.environ.get("ALLOW_UNPINNED", "")

    changed_files = [f.strip() for f in all_changed_files.split() if f.strip()]
    allow_unpinned = [a.strip() for a in allow_unpinned_str.split() if a.strip()]
    fail_on_error = fail_on_error_str.lower() in ("true", "1", "yes")

    sys.exit(validate_workflow_files(changed_files, allow_unpinned, fail_on_error))


if __name__ == "__main__":
    main()
