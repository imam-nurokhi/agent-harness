# Project Onboarding Checklist

Work through this once per repository, before an agent is allowed to change it.

## 1. Register
- [ ] Name, classification (cbqa / nexora / freelance / personal / sandbox)
- [ ] Local path under `~/AI-Workspace/projects/<class>/`
- [ ] Repository URL, default branch, development branch

## 2. Survey
- [ ] `ah recon <path>` run and the report read end to end
- [ ] Install / test / lint / build commands confirmed by running them yourself
- [ ] Anything the recon marked MISSING has been resolved or accepted

## 3. Contract
- [ ] `AGENTS.md` added at the repo root: stack, commands, architecture boundaries,
      business rules, dangerous commands, definition of done
- [ ] Commands in `AGENTS.md` verified to work — an agent will trust them literally

## 4. Safety
- [ ] No production credential anywhere in the working tree
- [ ] `.env.example` present; real `.env` git-ignored
- [ ] Database pointed at local or read-only staging
- [ ] Production deploy path unavailable to agents

## 5. First real task
- [ ] A small, isolated task run end to end: task → worktree → implement → review
- [ ] Diff reviewed by a human; no unintended changes
- [ ] Only then: promote to normal use
