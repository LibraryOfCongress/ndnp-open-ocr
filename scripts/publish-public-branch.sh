#!/usr/bin/env bash
# scripts/publish-public-branch.sh
# Create clean local public branch with internal files removed.

SRC_BRANCH="${SRC_BRANCH:-CHRONAM-2698-github-push}"
PUBLIC_BRANCH="${PUBLIC_BRANCH:-public}"

DENYLIST=(
  .gitlab-ci.yml
  terraform.tfstate.d
  OSS_READINESS_REPORT.md
  NOTES.md
  INTERNAL_README.md
  packages/cli/INTERNAL_README.md
  backend.hcl
  .env
  packages/cli/config.py
  scripts/publish-public-branch.sh
)

git switch "$SRC_BRANCH"
git branch -D "$PUBLIC_BRANCH" 2>/dev/null || true
git checkout --orphan "$PUBLIC_BRANCH"

for path in "${DENYLIST[@]}"; do
  git rm -rq --cached --ignore-unmatch "$path" 2>/dev/null || true
done

git commit -qm "Public snapshot of ${SRC_BRANCH}"

echo "✅ Created local '${PUBLIC_BRANCH}' ($(git ls-files | wc -l | tr -d ' ') files)"
echo "   Review then push when ready."