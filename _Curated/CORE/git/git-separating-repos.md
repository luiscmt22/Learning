# Separating a Project Into Its Own Repository

## Context
When two projects (HRModule and Joti) share the same Git repo and remote, versioning gets messy. Here's how to cleanly separate them while preserving full commit history.

---

## Step 1: Repoint the remote to a new repo

First, create the new empty repo on GitHub. Then change where `origin` points:

```bash
git remote set-url origin https://github.com/luiscmtAgile/Joti.git
```

## Step 2: Push full history to the new repo

```bash
git push -u origin master
```

This pushes all commits and sets up tracking. The new repo now has the complete history.

## Step 3: Remove a commit from the old repo

Add the old repo as a temporary remote:

```bash
git remote add hrmodule https://github.com/aginternal/HRModule.git
git fetch hrmodule
```

Inspect the history to find the right commit:

```bash
git log hrmodule/master --oneline -10
```

### The key trick: push a specific commit to a remote branch

```bash
git push hrmodule 019bcea:master --force
```

**What this does:** Pushes commit `019bcea` directly to `hrmodule/master`, effectively resetting it to that point. The Joti-specific commit (`e056b9c`) is removed from HRModule.

**Why this is powerful:**
- No `git checkout` needed — stays on your current branch
- No branch switching — your working tree is untouched
- Uncommitted local changes are safe
- You're manipulating the remote without affecting local state

### Syntax breakdown

```
git push <remote> <commit-sha>:<remote-branch> --force
```

| Part              | Meaning                                      |
|-------------------|----------------------------------------------|
| `<remote>`        | The remote to push to (e.g. `hrmodule`)      |
| `<commit-sha>`    | The exact commit you want the branch to be at |
| `:<remote-branch>`| The branch on the remote to update            |
| `--force`         | Required because you're rewriting history     |

## Step 4: Clean up

Remove the temporary remote:

```bash
git remote remove hrmodule
```

Verify:

```bash
git remote -v
# Should only show the new Joti origin
```

---

## Final State

| Repo      | Remote URL                                    | Latest Commit |
|-----------|-----------------------------------------------|---------------|
| Joti      | `https://github.com/luiscmtAgile/Joti.git`   | Full history   |
| HRModule  | `https://github.com/aginternal/HRModule.git` | Without Joti commits |

Both repos now have completely independent versioning.
