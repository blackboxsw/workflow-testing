#!/bin/bash
set -euo pipefail

echo "Checking for 'uses:' statements without SHA pins..."

fail=0
for file in $ALL_CHANGED_FILES; do
  if [ ! -f "$file" ]; then
    continue  # Skip if file doesn't exist (e.g. deleted files)
  fi
  if [[ $file != *.gthub/workflows/* ]]; then
    continue # Not a workflow file
  fi
  # Read non-null uses: values
  readarray -t USES_VALUES <<< $(cat ${file} | yq -r '.jobs[].steps.[].uses | select(.)')
  readarray -t USES_LINE_NUMS <<< $(cat ${file} | yq -r '.jobs[].steps.[].uses | select (.) | line')
  for uses_value in "${USES_VALUES[@]}"; do
    line_num=${USES_LINE_NUMS[0]}  # get line for this value
    USES_LINE_NUMS=("${USES_LINE_NUMS[@]:1}")  # pop first USES_LINE_NUMS item
    [[ "$uses_value" =~ .+@[a-f0-9]{40} ]] && continue  # valid 40-char SHA pin
    if [[ " ${ALLOW_UNPINNED[*]} " =~ " ${uses_value} " ]]; then
      echo "Ignoring allowed-unpinned: $uses_value"
      continue
    fi
    fail=1
    if [[ "$uses_value" =~ .+@.+ ]]; then
      echo "[$file:$line_num] ❌ ERROR: Invalid PIN type: $uses_value"
    else
      echo "[$file:$line_num] ❌ ERROR: No PIN found: $uses_value"
    fi
  done
done
    
if [ "$fail" -eq 1 ]; then
  echo "❌ Some workflows are using tags or branches instead of commit SHAs."
  echo "Best practice: pin SHAs with comment for tag/branch <some_action>@<commit_SHA> # v4"

  if [ "${FAIL_ON_ERROR}" = "true" ]; then
    exit 1
  fi
else
  echo "✅ All 'uses:' statements are correctly pinned to SHAs."
fi
