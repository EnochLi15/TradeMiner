# Issue Tracker: GitHub

Issues and PRDs for this repo live as GitHub issues in `EnochLi15/TradeMiner`. Use the `gh` CLI for all issue operations.

## Conventions

- Create an issue: `gh issue create --title "..." --body "..."`
- Read an issue: `gh issue view <number> --comments`
- List issues: `gh issue list --state open --json number,title,body,labels,comments`
- Comment on an issue: `gh issue comment <number> --body "..."`
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`
- Close an issue: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside this clone.

## When A Skill Says "Publish To The Issue Tracker"

Create a GitHub issue in `EnochLi15/TradeMiner`.

## When A Skill Says "Fetch The Relevant Ticket"

Run `gh issue view <number> --comments`.
