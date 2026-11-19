# Application Versioning

The application version is defined in `app/__init__.py` as `__version__`.
`/api/health`, `/api/about`, and full-backup metadata use that value.

## Choosing the next version

Use `MAJOR.MINOR.PATCH`. Choose the highest-impact change included in a release.

| Change in the release | Bump | Example from 0.9.9 |
| --- | --- | --- |
| Compatible bug fix, security fix, performance improvement, translation, or visual adjustment | Patch | 0.9.10 |
| New feature or capability that preserves existing supported behavior and data compatibility | Minor; reset patch to zero | 0.10.0 |
| Breaking API, configuration, import/export, or persisted-data contract requiring users or integrations to adapt | Major; reset minor and patch to zero | 1.0.0 |

Apply these rules while the application is at `0.x` too. Explain the choice in
the release summary. A release containing both fixes and a compatible feature
gets one minor bump, rather than a separate bump for each change.

Repository instructions, backlog entries, skills, and tests alone do not require
an application-version bump when they leave shipped application behavior
unchanged. Do not relabel old commits or deployments retroactively.

Application releases and financial-model, cache, backup-format, or workflow
schema versions are separate. Change a model or schema version only when its
own contract changes, following the relevant maintained project instructions.

## Release procedure

1. Review the complete release scope and select patch, minor, or major using the
   table above. Compare against the version in the latest application release.
2. Before releasing application changes, update `__version__` in
   `app/__init__.py` and include that file in the explicit task-owned release
   file list. Keep one version bump for the whole release, including when
   several commits are being released together.
3. Complete applicable tests and update affected Help and Hebrew translations.
   Use the established `cad` commit-and-deploy workflow when release is requested.
4. After deployment, verify that `/api/health` and `/api/about` report the version
   in the release commit, in addition to the normal deployed-file and functional
   checks. Report the version, commit, and deployment result.
5. If tests fail before a commit is created, keep the prepared version while
   fixing the same release. If the commit exists but deployment fails, inspect
   the current state and finish deploying that commit without bumping again
   merely for a retry. A later application-changing release gets a new version.

The release script does not automatically choose or increment the version.
The release owner performs this step; project instructions and the `cad` skill
make it part of the release checklist. This policy does not authorize deployment
on its own.
