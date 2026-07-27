# Contributing

## Core rules

1. Never commit directly to `main`/`master`; always branch from `main`/`master`
2. Do not commit, push, or open a PR without the user's explicit permission
3. Never `git push --force` to `main`/`master`
4. If the scope of a change is unclear, ask the user first

## Branch naming

```
feat/<short-description>    # New feature
fix/<short-description>     # Bug fix
docs/<short-description>    # Documentation
```

## Commit conventions

```
<type>(<scope>): <subject>

<body>

<footer>
```

- **type**
  - feat | fix | docs | style | refactor | tweak | perf | test | chore | ci | revert

- **subject**
  - Imperative mood, no trailing period, at most 50 characters
  - Atomic commits: one logical change per commit

- **breaking change**
  - Append `!` after the type, e.g. `feat!:`

- **docs type**
  - Must not include code/logic changes

## PR workflow

```bash
# 1. Push the branch
git push -u origin HEAD

# 2. Create the PR
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
- <key changes>

## Test plan
- [ ] <verification steps>
EOF
)"
```

## If a rule is broken

1. Stop the current action
2. Report which rule was violated
3. Propose a fix
4. Wait for the user's confirmation
