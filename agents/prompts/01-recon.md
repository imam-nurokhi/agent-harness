# Prompt: Repository Recon (read-only, always the first task on a new repo)

You are in read-only mode. Do not modify, create, or delete any file. Do not run
any command that writes, installs, or fetches.

Produce a Markdown report:

1. **Stack** — languages, frameworks, versions (from manifest files, not guesses).
2. **Entry points** — how the app starts, where routes/controllers live.
3. **Architecture** — the 5-8 directories that matter and what each owns.
4. **Commands** — install, run, test, lint, build. Quote the exact command and
   say where you found it (package.json script, Makefile, README, composer.json).
   Mark any you could not find as MISSING.
5. **Data** — database, migration tool, where the schema lives.
6. **Config and secrets** — which env vars are required; whether `.env.example`
   exists; whether any secret is currently committed (report the file, never the value).
7. **Top 5 technical risks** — ordered, each with evidence (file:line).
8. **Three safe starter tasks** — small, isolated, valuable, each with acceptance criteria.

End with: "Files modified: none."
