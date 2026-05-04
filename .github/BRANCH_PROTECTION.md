# Branch Protection Configuration for `master`

This document outlines the branch protection rules that should be configured on the `master` branch in GitHub. These settings enforce CI/CD quality gates and code review standards.

## Required Configuration

Configure these settings in **Settings → Branches → Branch protection rule (master)**:

### 1. Require a pull request before merging
- **✓ Require pull request reviews before merging**
  - Required number of reviewers: **1**
  - ✓ Dismiss stale pull request approvals when new commits are pushed
  - ✓ Require review from code owners (if CODEOWNERS file exists)

### 2. Require status checks to pass
- **✓ Require status checks to pass before merging**
  - Required checks:
    - `lint-test-build` (from `.github/workflows/ci.yml`) — must pass
    - `validate-bicep` (from `.github/workflows/bicep-validate.yml`) — should pass on `infra/**` changes

### 3. Additional protections
- ✓ **Require branches to be up to date before merging**
- ✓ **Restrict who can push to matching branches**
  - Allow force pushes: No
  - Dismiss pull request reviews: Enabled

### 4. Non-enforced (optional, for consideration)
- Require approval of reviews from code owners
- Require conversation resolution before merging
- Require deployments to succeed before merging

## CLI Command (if admin access available)

```bash
gh api repos/frdeange/verdecoraTest/branches/master/protection \
  --input - <<'EOF'
{
  "required_pull_request_reviews": {
    "dismissal_restrictions": null,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint-test-build", "validate-bicep"]
  },
  "enforce_admins": true,
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

**Note:** This requires admin or maintain role. If you have write-only access, ask a repository admin to configure these settings.

## Enforcement Timeline

- **Immediate (Day 1):** All PRs to `master` must have CI passing
- **Week 1:** Require 1 manual review from dev team
- **Week 2+:** Add code owner approval if CODEOWNERS file is created
