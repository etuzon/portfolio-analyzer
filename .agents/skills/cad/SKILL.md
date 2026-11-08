---
name: cad
description: Commit and deploy the current portfolio-analyzer task when the user invokes cad or explicitly requests commit and deploy.
---

# Commit and deploy

Use the existing release workflow in `/etuzon/projects/ai/portfolio-analyzer`.
Invoke this workflow with `$cad` or the legacy custom prompt `/prompts:cad`.
These instructions do not register a native bare `/cad` slash-menu command.
An explicit invocation of this workflow authorizes committing and deploying the
current task to this project's established local Docker Compose target. Creating
or editing the shortcut is not a request to release anything.

1. Read the repository's `AGENTS.md` and inspect Git status and the relevant diff.
   Identify the current task's changes from the conversation and any supplied
   scope. Keep unrelated changes intact and out of both the commit and deployment
   build, including unrelated edits within a selected file. Never stage everything
   indiscriminately. Exclude secrets and generated runtime data.
2. Finish necessary implementation and validation before release. Use a supplied
   commit message when appropriate; otherwise write a concise message describing
   the actual change. Do not ask again for release permission already conveyed by
   the invocation. Ask only when the intended scope or deployment target cannot
   be determined from the conversation and repository.
   For every functionality added, changed, or removed in the release, verify that
   the affected in-app Help and both language versions have been updated in the
   same task. Follow the Help-maintenance rule in the `portfolio-analyzer` skill;
   resolve outdated or missing usage instructions before running the release.
3. From the project root, run the existing release script with explicit,
   repository-relative file paths:

   ```bash
   ./scripts/commit-and-deploy.sh --quiet "Describe the change" path/to/file path/to/another-file
   ```

   Preserve an existing custom bridge directory by passing its host mount source
   as `PORTFOLIO_CODEX_DIR` to the entire release command. On this workstation,
   `/tmp/portfolio-codex` is root-owned; use
   `PORTFOLIO_CODEX_DIR=/tmp/portfolio-codex-etuzon` unless the running app's
   `/run/portfolio-codex` mount establishes a different usable path. The same
   override must reach both the bridge helper and Docker Compose.

   This script runs pytest, commits the selected files, rebuilds Docker Compose,
   and checks `https://localhost:6443/api/health`. Follow its gates. If a gate
   fails, diagnose and fix failures within the task's scope; do not bypass it or
   blindly rerun a partially completed release. If it already created the commit,
   inspect that state before continuing the remaining deployment steps.
4. Use quiet mode for routine releases. The script waits for its child, preserves
   failure exit codes, saves verbose output in a private Git-ignored
   `.runtime/releases/` log, and emits only a short success summary or bounded
   failure tail. It checks HTTPS health and verifies selected deployed application
   files and served assets against the commit using `scripts/verify-deployment.py`.
   Let these deterministic checks run in the script; do not repeatedly read full
   test/build logs or recreate the same checks with ad hoc AI-generated commands.
   Wait for the running tool to finish with a small output budget; tool-status
   waits may still be needed by the client. Inspect the log only on failure or
   when a task-specific concern remains. Do not call Codex/another model to
   monitor a release.
   Complete task-specific behavioral QA before release and include any required
   deployment-specific checks that are not covered by the generic source/health
   checks. Report the commit, script result and material verification limits. Do not push to a remote, merge a
   branch, or change another deployment target unless separately requested.
