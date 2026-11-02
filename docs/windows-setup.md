# Windows setup and Git workflow

A step-by-step guide for working with this project on Windows, written for someone new to Git. Run every command in PowerShell (Start menu, type `PowerShell`).

## 1. Install the tools

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
winget install --id Casey.Just -e      # optional: shortcuts such as `just test`
```

Close and reopen PowerShell, then check:

```powershell
git --version
uv --version
just --version
```

If `winget` is unavailable, download the installers from the Git for Windows, uv and just websites. The uv installer script also works: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`. You do not need to install Python: uv downloads the right version.

## 2. Clone from the bundle file

The project may be handed to you as a single file, `tipping-early-warning.bundle`, which contains the whole history. Put it in a folder, open PowerShell there and run:

```powershell
git clone tipping-early-warning.bundle tipping-early-warning
cd tipping-early-warning
uv sync --locked --group dev --extra deck
uv run pytest
```

If the tests pass, the environment is working. After cloning, `origin` points at the bundle file; step 4 replaces it.

## 3. Set your identity and re-author the commits

Git stamps every commit with a name and an e-mail address. The identity stored in the original repository does not travel inside the bundle, so set your own, for this repository only (no `--global` flag):

```powershell
git config user.name "Your Name"
git config user.email "you@example.com"
```

The existing commits still carry the original author. To rewrite them under your identity:

```powershell
git rebase -r --root --exec "git commit --amend --reset-author --no-edit"
```

Warning: this rewrites history. Every commit gets a new hash. Do it once, right after cloning and before the first push to GitHub. Never do it on a branch other people have already pulled. Two follow-ups:

- Tags are not moved by a rebase. If the repository already has a tag such as `v0.1.0`, point it at the new last commit: `git tag -f v0.1.0`.
- Check the result with `git log --format="%h %an <%ae> %s"`; every line should show your identity.

If the rebase stops with a conflict message, run `git rebase --abort` to return to where you started.

## 4. Create the GitHub repository and push

1. On github.com, choose New repository. Name it `tipping-early-warning`. Leave it empty: do not add a README, `.gitignore` or license.
2. Replace the bundle remote with the GitHub one and push everything, including tags:

```powershell
git remote remove origin
git remote add origin https://github.com/<your-user>/tipping-early-warning.git
git push -u origin main --tags
```

Git for Windows includes Git Credential Manager: the first push opens a browser window to sign in. Afterwards, `git push` alone is enough.

## 5. Daily workflow: branch, commit, pull request

Never commit straight to `main`. Work on a short-lived branch and merge it through a pull request.

```powershell
git switch main
git pull
git switch -c feat/rolling-window-option      # new branch

# edit files, then:
just check                                    # lint, typecheck, tests
git status                                    # see what changed
git add src/tipping/indicators.py tests/test_indicators.py
git commit -m "feat(indicators): add configurable window overlap"

git push -u origin feat/rolling-window-option
```

On GitHub a banner offers Compare and pull request. Fill in the template, wait for the CI checks (Linux and Windows) to turn green and merge. Then update your local copy:

```powershell
git switch main
git pull
git branch -d feat/rolling-window-option
```

Stage files by name with `git add <paths>` rather than `git add .`, so that nothing generated (`data/`, `results/`, `deck/build/`) is committed by accident. These folders are already ignored.

### Conventional Commits cheat sheet

Format: `type(optional scope): short description in the imperative`, for example `fix(model): use cbrt for negative radicands`.

| Type | Use for |
| --- | --- |
| `feat` | new functionality |
| `fix` | bug fix |
| `docs` | documentation only |
| `test` | adding or changing tests |
| `refactor` | code change without behaviour change |
| `chore` | tooling, dependencies, housekeeping |
| `ci` | continuous-integration configuration |

Keep the first line under about 72 characters, in English, without a trailing period. Add a blank line and a longer explanation only when the reason for the change is not obvious.

## 6. Tag v0.1.0 and publish a release

After the final commit is on `main` and the checks are green:

```powershell
git switch main
git pull
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Build the deck and the animations first, so that the files exist:

```powershell
just reproduce
just deck
```

Then on GitHub: Releases, Draft a new release, choose the tag `v0.1.0`, give it a title and a short description (the matching section of `CHANGELOG.md` works well). Drag the deck PDF and the MP4 files from `deck/build/` into the attachment area and publish. The binaries live in the release, not in the repository, which keeps the repository small.

## Troubleshooting

- `uv` or `just` is not recognised: close and reopen PowerShell so the updated PATH is loaded.
- Script execution is blocked: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- Git warns about line endings (`LF will be replaced by CRLF`): harmless; `.gitattributes` controls the normalisation.
- `git push` is rejected: run `git pull --rebase` first, then push again.
