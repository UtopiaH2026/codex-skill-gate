# Architecture

```text
SKILL.md files
    |
    v
indexer.py ------> index.json
    |
    v
UserPromptSubmit hook
    |
    +-- state.py: sticky coding state
    |
    +-- classifier.py: deterministic coding/non-coding decision
    |
    +-- catalog.py: compact skill catalog
    |
    v
additionalContext for the current model turn
```

## Scope

V1 intentionally supports only file-backed `SKILL.md` sources:

- `$CODEX_HOME/skills`;
- enabled plugin skill directories under `$CODEX_HOME/plugins/cache`;
- nearest project `.codex/skills` or `.agents/skills`;
- optional extra roots from `config.json`.

Orchestrator, remote, and custom resource skills are out of scope.

## Index Schema

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-30T00:00:00+00:00",
  "roots": [],
  "skills": [
    {
      "name": "example",
      "description": "Short trigger description",
      "path": "C:/Users/me/.codex/skills/example/SKILL.md",
      "scope": "user",
      "source": "user skills",
      "mtime_ns": 0
    }
  ]
}
```

Duplicate skill names are resolved by discovery precedence: user, repository, system/plugin.

## State Machine

```text
unknown --coding signal--> coding
unknown --no signal------> non_coding
coding  --normal prompt--> coding       (sticky)
coding  --explicit off---> non_coding
non_coding --coding signal--> coding
```

State is keyed by `session_id`, falling back to a transcript-path hash.

## Classification Contract

The classifier is deterministic and local. It returns:

- `mode`: `coding` or `non_coding`;
- `score`: numeric confidence;
- `evidence`: short matched labels for debugging and tests.

Default threshold: `4.0`.

A strong coding match contributes six points. Medium matches contribute up to 4.5 points. Project markers contribute up to two points. Recent conversation history can contribute up to four points, including the continuation case.

Repository context alone contributes at most two points, so it never crosses the threshold by itself.

## Hook Contract

Input follows Codex `UserPromptSubmit` JSON. Output is either a no-op:

```json
{
  "continue": true,
  "suppressOutput": true
}
```

or a catalog injection:

```json
{
  "continue": true,
  "suppressOutput": true,
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "<skills_instructions>...</skills_instructions>"
  }
}
```

## Security

- The hook never executes a skill or a script from skill metadata.
- It reads only frontmatter-derived metadata during indexing.
- It strips angle brackets from metadata before injecting it.
- It runs with no network calls.
- Hook errors are logged and fail open.
