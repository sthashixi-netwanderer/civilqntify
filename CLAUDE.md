# CLAUDE.md — Project Guidelines for Claude Code

## Git Commit Rules

### Co-authored-by Policy
**DO NOT** add `Co-authored-by: Claude Code <noreply@anthropic.com>` or any similar co-author attribution to git commit messages. All commits should appear as authored solely by the user.

This applies to:
- Direct commits made by Claude Code
- Amended commits
- Squashed commits
- Any commit message templates

## Code Style

- Python 3.11+ compatible
- Type hints required for all function signatures
- Docstrings follow Google style
- Maximum line length: 88 characters (Black/ruff default)

## Testing

- Run tests with `pytest` before committing
- All tests must pass before pushing to main
