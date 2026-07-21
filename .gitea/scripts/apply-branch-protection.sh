#!/usr/bin/env bash
set -euo pipefail

skip_missing=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-missing)
      skip_missing=true
      shift
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 [--skip-missing] <org> <repo> <branch>" >&2
  exit 1
fi

org="$1"
repo="$2"
branch="$3"
api_url="${RENOVATE_ENDPOINT:-${GITEA_API_URL:-${GITHUB_API_URL:-}}}"
token="${ADMIN_TOKEN:-${GITEA_TOKEN:-}}"

if [[ -z "$api_url" ]]; then
  echo "Set RENOVATE_ENDPOINT to your Gitea API base URL, for example https://gitea.example.com/api/v1" >&2
  exit 1
fi
if [[ -z "$token" ]]; then
  echo "Set ADMIN_TOKEN to a Gitea personal access token with repository admin rights" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 1
fi

api_request() {
  local method="$1"
  local path="$2"
  local data="${3:-}"

  if [[ -n "$data" ]]; then
    curl --silent --show-error --fail \
      -X "$method" \
      -H "Authorization: token ${token}" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      --data "$data" \
      "${api_url}${path}"
    return
  fi

  curl --silent --show-error --fail \
    -X "$method" \
    -H "Authorization: token ${token}" \
    -H "Accept: application/json" \
    "${api_url}${path}"
}

if ! api_request GET "/repos/${org}/${repo}/branches/${branch}" >/dev/null 2>&1; then
  if [[ "$skip_missing" == "true" ]]; then
    echo "Skipping missing branch: ${org}/${repo}:${branch}"
    exit 0
  fi
  echo "Branch not found: ${org}/${repo}:${branch}" >&2
  echo "Create and push '${branch}' before applying branch protection." >&2
  exit 1
fi

payload="$(jq -nc --arg branch "$branch" '{
  branch_name: $branch,
  enable_push: false,
  enable_status_check: true,
  status_check_contexts: [
    "ci (push)",
    "build-validation (push)",
    "smoke-test (push)",
    "ci (pull_request)",
    "build-validation (pull_request)",
    "smoke-test (pull_request)"
  ],
  required_approvals: 0,
  dismiss_stale_approvals: false,
  ignore_stale_approvals: false,
  block_on_outdated_branch: false,
  block_on_rejected_reviews: true,
  block_on_official_review_requests: false,
  block_admin_merge_override: true,
  enable_merge_whitelist: false,
  enable_push_whitelist: false,
  enable_force_push: false,
  enable_force_push_allowlist: false,
  require_signed_commits: false
}')"

echo "Applying branch protection to ${org}/${repo}:${branch}"
if api_request GET "/repos/${org}/${repo}/branch_protections/${branch}" >/dev/null 2>&1; then
  api_request PATCH "/repos/${org}/${repo}/branch_protections/${branch}" "$payload" >/dev/null
else
  api_request POST "/repos/${org}/${repo}/branch_protections" "$payload" >/dev/null
fi

echo "branch protection applied"
