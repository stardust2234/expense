#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 4 ]]; then
  echo "Usage: $0 <owner> <repo> [head_branch] [base_branch]" >&2
  exit 1
fi

owner="$1"
repo="$2"
head_branch="${3:-development}"
base_branch="${4:-main}"
api_url="${RENOVATE_ENDPOINT:-${GITEA_API_URL:-${GITHUB_API_URL:-}}}"
token="${ADMIN_TOKEN:-${GITEA_TOKEN:-}}"

if [[ -z "$api_url" ]]; then
  echo "Set RENOVATE_ENDPOINT to your Gitea API base URL, for example https://gitea.example.com/api/v1" >&2
  exit 1
fi

if [[ -z "$token" ]]; then
  echo "Set ADMIN_TOKEN to a token with pull-request merge permissions" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

api_request() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local response
  local body
  local status

  if [[ -n "$data" ]]; then
    response="$(
      curl --silent --show-error \
        -X "$method" \
        -H "Authorization: token ${token}" \
        -H "Accept: application/json" \
        -H "Content-Type: application/json" \
        --data "$data" \
        --write-out $'\n%{http_code}' \
        "${api_url}${path}"
    )"
  else
    response="$(
      curl --silent --show-error \
        -X "$method" \
        -H "Authorization: token ${token}" \
        -H "Accept: application/json" \
        --write-out $'\n%{http_code}' \
        "${api_url}${path}"
    )"
  fi

  body="${response%$'\n'*}"
  status="${response##*$'\n'}"

  printf '%s\n%s' "$status" "$body"
}

read_response() {
  local result="$1"
  API_STATUS="${result%%$'\n'*}"
  API_BODY="${result#*$'\n'}"
}

find_pr_number() {
  API_BODY_JSON="$API_BODY" python3 - "$head_branch" "$base_branch" <<'PY'
import json
import os
import sys

head_branch = sys.argv[1]
base_branch = sys.argv[2]
body = os.environ.get("API_BODY_JSON", "[]")

try:
    pulls = json.loads(body)
except json.JSONDecodeError:
    print("")
    raise SystemExit(0)

for pull in pulls:
    head = ((pull.get("head") or {}).get("ref") or "").strip()
    base = ((pull.get("base") or {}).get("ref") or "").strip()
    if head == head_branch and base == base_branch:
        print(pull.get("number") or pull.get("index") or "")
        break
else:
    print("")
PY
}

branch_response="$(api_request GET "/repos/${owner}/${repo}/branches/${head_branch}")"
read_response "$branch_response"
if [[ "$API_STATUS" != "200" ]]; then
  echo "Unable to read ${head_branch}: ${API_BODY}" >&2
  exit 1
fi

head_sha="$(API_BODY_JSON="$API_BODY" python3 - <<'PY'
import json
import os

branch = json.loads(os.environ["API_BODY_JSON"])
print(branch["commit"]["id"])
PY
)"

pulls_response="$(api_request GET "/repos/${owner}/${repo}/pulls?state=open")"
read_response "$pulls_response"
if [[ "$API_STATUS" != "200" ]]; then
  echo "Unable to list pull requests: ${API_BODY}" >&2
  exit 1
fi

pr_number="$(find_pr_number)"

if [[ -z "$pr_number" ]]; then
  create_payload="$(python3 - "$head_branch" "$base_branch" <<'PY'
import json
import sys

head_branch = sys.argv[1]
base_branch = sys.argv[2]
payload = {
    "title": f"Promote {head_branch} to {base_branch}",
    "body": (
        "Automated promotion pull request created by Gitea Actions.\n\n"
        "This pull request is kept open and scheduled for auto-merge when the "
        "required status checks for the latest development commit succeed."
    ),
    "head": head_branch,
    "base": base_branch,
}
print(json.dumps(payload))
PY
)"

  create_response="$(api_request POST "/repos/${owner}/${repo}/pulls" "$create_payload")"
  read_response "$create_response"

  if [[ "$API_STATUS" == "201" ]]; then
    pr_number="$(API_BODY_JSON="$API_BODY" python3 - <<'PY'
import json
import os

pull = json.loads(os.environ["API_BODY_JSON"])
print(pull.get("number") or pull.get("index") or "")
PY
)"
    echo "Created promotion pull request #${pr_number} for ${head_branch} -> ${base_branch}."
  elif [[ "$API_STATUS" == "409" ]]; then
    pulls_response="$(api_request GET "/repos/${owner}/${repo}/pulls?state=open")"
    read_response "$pulls_response"
    if [[ "$API_STATUS" != "200" ]]; then
      echo "Unable to refresh pull requests after create conflict: ${API_BODY}" >&2
      exit 1
    fi
    pr_number="$(find_pr_number)"
    if [[ -z "$pr_number" ]]; then
      echo "No promotion pull request created. Gitea reported a conflict, which usually means there is nothing new to promote." >&2
      exit 0
    fi
  else
    echo "Unable to create promotion pull request: ${API_BODY}" >&2
    exit 1
  fi
fi

cancel_response="$(api_request DELETE "/repos/${owner}/${repo}/pulls/${pr_number}/merge")"
read_response "$cancel_response"
if [[ "$API_STATUS" == "204" ]]; then
  echo "Cleared existing auto-merge schedule for pull request #${pr_number}."
elif [[ "$API_STATUS" != "404" ]]; then
  echo "Unable to clear existing auto-merge schedule for pull request #${pr_number}: ${API_BODY}" >&2
  exit 1
fi

merge_payload="$(python3 - "$head_sha" <<'PY'
import json
import sys

payload = {
    "Do": "merge",
    "head_commit_id": sys.argv[1],
    "merge_when_checks_succeed": True,
    "delete_branch_after_merge": False,
}
print(json.dumps(payload))
PY
)"

merge_response="$(api_request POST "/repos/${owner}/${repo}/pulls/${pr_number}/merge" "$merge_payload")"
read_response "$merge_response"
if [[ "$API_STATUS" != "200" && "$API_STATUS" != "201" ]]; then
  echo "Unable to schedule auto-merge for pull request #${pr_number}: ${API_BODY}" >&2
  exit 1
fi

echo "Scheduled pull request #${pr_number} to auto-merge ${head_branch} into ${base_branch} after required checks succeed."
