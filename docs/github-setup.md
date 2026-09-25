# GitHub setup

Suggested repository name: `mma3001-composites-fatigue`. Default visibility: private. This package is the prepared local project; a GitHub remote has not been created by preparing these files.

## Place the project separately from the NASA files

Extract the package so that `README.md`, `scripts`, `results` and `tests` are directly inside:

```text
D:\Saneeh\Monash\Year 3\MMA3001\Projects\mma3001-composites-fatigue
```

Keep the existing dataset under `Projects\ll`. Do not copy the whole dataset into this new project folder. Preserve existing local analysis folders until you have verified the imported project.

## Initial commit and private remote

If Git and GitHub CLI are installed, run from the new project folder. First verify that it does not already have a repository/remote. Use your actual Git author identity; do not invent one or overwrite a global configuration.

```powershell
git --version
gh --version
git config user.name
git config user.email
```

If either author field is missing, set it for this repository after `git init`, using your chosen name and verified GitHub/noreply email. Then:

```powershell
git init -b main
git add README.md LICENSE .gitignore .gitattributes requirements.txt scripts tests docs data archive results/baseline
git diff --cached --stat
git commit -m "Import composites fatigue feasibility study"
gh auth login
gh repo create mma3001-composites-fatigue --private --source . --remote origin --push
```

Complete authentication in the GitHub sign-in flow; do not paste tokens into code or chat. If a repository with that name already exists, inspect it before reusing it. Do not force-push or overwrite an existing remote.

If GitHub CLI is not installed, create a new empty private repository on GitHub, without an additional README, licence or gitignore. After the local commit, use the exact remote URL GitHub supplies:

```powershell
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

`YOUR_REPOSITORY_URL` is a placeholder. [GitHub CLI's official create documentation](https://cli.github.com/manual/gh_repo_create) describes the existing-source and private-repository options.

## Subsequent work

```powershell
git status
git add scripts docs tests
git diff --cached
git commit -m "Describe the actual change"
git push
```

Stage small result files explicitly when they belong to an experiment. `.gitignore` ignores regenerated/sensitivity outputs by default; review them before deciding what to track. Do not change repository visibility as part of a routine code update.
