[![CI](https://github.com/UtopiaH2026/codex-skill-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/UtopiaH2026/codex-skill-gate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

# Codex Skill Gate

**The first public binary gate for Codex skill metadata: coding sessions get the catalog, everything else gets zero skill metadata.**

> Novelty statement, verified 2026-09-30: no existing public project was found that combines `skills.include_instructions = false`, an automatic coding/non-coding classifier, a `UserPromptSubmit` hook, and sticky per-session state. Adjacent prior art is documented in [docs/prior-art.md](docs/prior-art.md).

## The Problem

Every installed Codex skill consumes context on every turn. With 10 skills this is tolerable. With 100+ skills, the skill catalog becomes a metadata tax paid by every prompt, including prompts that have nothing to do with the available skills.

Codex already truncates this catalog to a hard context budget, but truncation does not remove the cost. It only reduces or degrades descriptions.

## The Idea

Codex Skill Gate takes a deliberately narrow first step:

1. Disable the complete built-in skill catalog with `skills.include_instructions = false`.
2. Classify each session as `coding` or `non_coding`, with `non_coding` as the default.
3. In a non-coding session, inject no skill metadata at all.
4. When coding is detected, inject the full compact skill catalog through a `UserPromptSubmit` hook.
5. Once a session becomes coding, keep that state for the rest of the session.

This is intentionally different from relevance-based routers. V1 answers one high-value question first: **is this a coding environment?** It does not try to choose a perfect skill before the model has enough context.

## Flow

```text
User prompt
   |
   v
UserPromptSubmit hook
   |
   +-- non-coding ------------------> no skill metadata
   |
   +-- coding ----------------------> compact full skill catalog
                                         |
                                         v
                                   model reads matching SKILL.md

Session state: non_coding -> coding becomes sticky until reset
```

## Install

Requirements:

- Codex with `UserPromptSubmit` hook support
- Python 3.11 or newer

From a clone of this repository:

```bash
python -m skill_gate install --dry-run
python -m skill_gate install
skill-gate doctor
```

On Windows PowerShell, the same commands work. A wrapper is also available:

```powershell
./scripts/install.ps1 -DryRun
./scripts/install.ps1
```

Project-scoped installation:

```bash
python -m skill_gate install --scope project --project-root .
```

User-scoped installation is the default. The installer:

- backs up the existing `config.toml`;
- merges `skills.include_instructions = false`;
- installs a managed hook block for `UserPromptSubmit`;
- copies the runtime to `$CODEX_HOME/skill-gate` or `./.skill-gate`;
- builds the initial skill index;
- leaves unrelated configuration intact.

After installation, restart Codex or open a new thread so the hook is loaded and trusted.

Uninstall:

```bash
python -m skill_gate uninstall
skill-gate uninstall --scope project --project-root .
```

## Publish This Repository

Create a clean commit first, then set `GITHUB_TOKEN` with repository creation permission:

```bash
python scripts/publish_github.py --repo codex-skill-gate
```

The publisher creates the public repository when needed, configures `origin`, and pushes `HEAD` to `main`. Use `--private` for a private repository.
## Try Without Installing

```bash
python -m skill_gate classify "Fix the Python bug in this function"
python -m skill_gate classify "写一篇关于秋天的散文"
python -m skill_gate index --json
python -m skill_gate hook --prompt "修复这个 TypeScript 报错"
```

Classification output includes the score and the exact evidence used.

## Classification Signals

Strong signals immediately enter coding mode:

- fenced code or recognizable function/class declarations;
- tracebacks, exceptions, compiler errors, and stack traces;
- coding verbs combined with code nouns;
- Git, package-manager, test-runner, and build-tool commands;
- code-file extensions and pull-request/code-review language.

Medium signals accumulate toward the threshold:

- programming languages, frameworks, databases, containers, and deployment tools;
- backend/frontend, algorithms, CLI, compiler, crawler, and automation terminology;
- recent conversation history;
- project markers such as `.git`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `src/`, and `tests/`.

Important: a repository-shaped cwd alone is **not** enough. A request for a poem or a report inside a code repository remains non-coding.

Explicit escape hatches:

- Enter coding mode: `进入编程模式`
- Leave coding mode: `退出编程模式`
- Reset one session: `skill-gate reset --session-id <id>`

## Configuration

The generated configuration lives at:

- user scope: `$CODEX_HOME/skill-gate/config.json`
- project scope: `./.skill-gate/config.json`

Example:

```json
{
  "classifier": {
    "threshold": 4.0,
    "sticky": true,
    "lookback_user_messages": 2,
    "extra_strong_patterns": [],
    "extra_medium_patterns": []
  },
  "catalog": {
    "max_tokens": 4000,
    "description_chars": 120
  }
}
```

Add project-specific vocabulary through `extra_strong_patterns` or `extra_medium_patterns`. Invalid regular expressions are ignored.

## What Is Stored

The index stores only file-backed skill metadata:

- skill name;
- description;
- absolute `SKILL.md` path;
- source scope;
- modification time.

Skill bodies are not loaded by the hook. The model reads a selected `SKILL.md` only after the catalog is injected.

State is stored per session:

```text
$CODEX_HOME/skill-gate/state/<session-id>.json
```

There is no network request and no telemetry.

## Safety and Failure Behavior

- Hook failures fail open and never block a user prompt.
- The installed hook has a five-second timeout.
- A missing or stale index is rebuilt before injection.
- If index rebuilding fails, no catalog is injected.
- Skill descriptions are stripped of angle brackets before insertion.
- The uninstaller removes only the managed hook block and restores the previous `include_instructions` value.

## Prior Art

The broader ideas are not new. Codex Skill Gate is the binary-gating combination, not the first lazy-loading system in the ecosystem. See [docs/prior-art.md](docs/prior-art.md) and [docs/architecture.md](docs/architecture.md).

Closest references:

- [openai/codex#21425](https://github.com/openai/codex/issues/21425) requests on-demand skill metadata injection.
- [SDeenAdmin/skill-valet](https://github.com/SDeenAdmin/skill-valet) parks and restores skill directories per prompt.
- [underdown/lazy-load-skills](https://github.com/underdown/lazy-load-skills) injects a relevance-ranked shortlist.
- [zenobi-us/opencode-skillful](https://github.com/zenobi-us/opencode-skillful) loads skills only after explicit tool calls.
- [fworks-tech/agenthood#614](https://github.com/fworks-tech/agenthood/issues/614) proposes lazy metadata loading.

## Roadmap

- Add a measured evaluation corpus for coding/non-coding classification.
- Add project-level rule packs.
- Add optional PostCompact re-injection.
- Add a top-K mode for very large coding catalogs.
- Add Windows installer packaging.

## Development

```bash
python -m unittest discover -s tests -v
python evals/run_eval.py --cwd .
python -m compileall skill_gate
```

Plugin validation is performed with Codex's plugin validator when available.

## License

MIT

