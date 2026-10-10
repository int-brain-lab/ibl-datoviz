# Working in ibl-datoviz

Read `docs/NEXT_STEPS.md` for completed work, validation evidence, and remaining release gates.
Use `docs/REAL_DATA_EXAMPLE_ROADMAP.md` for interactive review criteria. Preserve the public API
and native ownership contracts: retained arrays must own their storage; scene-owned resources,
GUI handles, callback subscriptions, and worker shutdown must keep their documented lifetimes.

## Contributor commands (macOS and Linux)

Run commands from this repository. `just` lists recipes; `uv` manages the locked environment.
Datoviz is cloned, built, and configured separately. Local setup/test/review commands use the
configured checkout and warn when its revision differs from the immutable pin in `pyproject.toml`
and `uv.lock`. Use `just doctor --strict`, `just test --strict`, and `just review all --strict`
for baseline validation. Do not build Datoviz, switch its revision, or change the pin just
to make a package check pass. Baseline upgrades require an explicit decision and compatibility
validation; the current baseline is recorded in `docs/NEXT_STEPS.md`.

```sh
just setup-tests /path/to/datoviz  # initial setup for unit/native tests
just doctor                      # check configured source and loaded library
just test                        # full suite
just test tests/test_probe_replacement.py -q  # focused pytest arguments
just lint
just docs                        # strict MkDocs build
git diff --check
```

For real-data review, use `just setup /path/to/datoviz` instead of `setup-tests`, then
`just review` (close each window to advance) or `just review picking`. Available examples are
`surface`, `mapping`, `picking`, `probe`, `firing-rate`, and `slices`. A bounded startup check is
`just review all --frames 3`; on headless Linux use `xvfb-run -a just review all --frames 3`.
Startup checks do not establish interaction quality. Actual macOS rendering requires Mac evidence.

Setup persists the local path in ignored `build/review/config.json`, caches pinned anatomy fixtures
under `build/review/anatomy`, and optionally prepares D070 and 50 um review assets. Quote paths
containing spaces. The helper discovers `.dylib` on macOS and `.so` on Linux and selects matching
Python bindings. Configure/allow Datoviz's `.envrc` separately if using `direnv`; the helper never
auto-approves it. See `docs/getting-started.md` for prerequisites and direct `uv` equivalents.

Keep recipes thin; runtime discovery, downloads, and filesystem operations belong in
`tools/review.py`. Forward recipe arguments through quoted positional parameters, not shell-code
interpolation. Validate recipe changes with `just --dump`, discovery, and argument forwarding.
Do not assume a sibling anatomy checkout or embed workstation-specific paths in tracked files.
Keep CI's pinned fixture setup working. Report test skips and missing GPU/asset evidence explicitly.

Validate changes with appropriate focused tests and required checks, update the handoff as work
lands, and commit in focused steps. Gallery/benchmark outputs belong in ignored `build/`;
review images before explicitly publishing canonical documentation assets. The bundled registered
graph has sampled sections and cannot start the unrestricted navigator; do not silently substitute
scientific data or present it as complete coverage.

<!-- codex-workbench:github-identity:start -->
## GitHub identity before writes

Before every GitHub write, including comments, reviews, edits and deletions,
resolve the expected account from the target repository's configured SSH remote:

- `git@github.com:OWNER/REPO.git` (or equivalent `ssh://` URL): `rossant`.
- `git@github.adikia:OWNER/REPO.git` (or equivalent `ssh://` URL): `association-adikia`.

This is an explicit personal routing convention, not automatic GitHub CLI
behavior. Apply it to the repository being acted on, not an unrelated current
directory. Inspect both fetch and push URLs for the selected remote (normally
`origin`). If they imply different accounts, or the URL is HTTPS, unknown or
unavailable, stop and resolve the expected identity with the user before writing.
Honor a more specific repository identity rule; stop if it conflicts with the
remote mapping. Never infer the account from the repository owner, Git commit
name/email, the AI account/profile, or an earlier successful identity check.

For GitHub CLI, obtain the expected account's credential with
`gh auth token --hostname github.com --user EXPECTED_LOGIN`, capture it without
printing it, and set `GH_TOKEN` for both the verification and the write command.
Verify `gh api --hostname github.com user --jq .login` equals the expected login
immediately before each write using that same credential. This avoids another
session changing the shared active account between verification and posting.
Use `github.com` as the API host; `github.adikia` is an SSH alias only.
Never print tokens, store them in repository files, or enable shell tracing.

For connectors and browser sessions, verify their own authenticated user before
each write. A CLI identity check does not establish a connector/browser identity.
If the expected identity cannot be verified, stop without writing and report the
blocker. This policy does not authorize posting without the user's instruction.
<!-- codex-workbench:github-identity:end -->
