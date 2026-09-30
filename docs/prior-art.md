# Prior Art

This project was checked against public GitHub repositories and issues on **2026-09-30**.

No exact public match was found for this combination:

1. default-off Codex skill metadata;
2. deterministic coding versus non-coding classification;
3. `UserPromptSubmit` hook re-injection;
4. sticky coding state per session;
5. full compact catalog rather than a Top-K shortlist.

Several adjacent projects already exist.

| Project | Overlap | Difference |
|---|---|---|
| [openai/codex#21425](https://github.com/openai/codex/issues/21425) | Requests separation of installed capability from per-session injection, including `on_demand` and lazy loading | Product-level proposal, not an implementation; no binary coding/non-coding gate |
| [SDeenAdmin/skill-valet](https://github.com/SDeenAdmin/skill-valet) | `UserPromptSubmit` hook moves skill directories in and out mid-session | Group keywords and idle parking; not default-zero; global directory movement |
| [underdown/lazy-load-skills](https://github.com/underdown/lazy-load-skills) | Hook selects Top-N skills before the LLM call and injects ephemeral context | Does not remove the original full skill catalog, so the metadata tax remains |
| [zenobi-us/opencode-skillful](https://github.com/zenobi-us/opencode-skillful) | Skills are not injected until an explicit tool request | Explicit `skill_find`/`skill_use` workflow, not automatic classification |
| [akcodes9/skillfish-router](https://github.com/akcodes9/skillfish-router) | Computes a minimum skill set for each prompt through a hook plus MCP server | Routing assumes a capability catalog; not a binary metadata on/off gate |
| [captain-d-red/skill-router](https://github.com/captain-d-red/skill-router) | Prompt keyword scoring produces a small candidate shortlist | Skills are already available to the model; no catalog gating |
| [by-sonic/skill-compass](https://github.com/by-sonic/skill-compass) | Reads project stack, prompt, and tool results to select coding skills | Coding-only optimizer; does not unload the base skill catalog |
| [all666666all/OpenClaw-Skill-Manager](https://github.com/all666666all/OpenClaw-Skill-Manager) | Progressive three-tier loading with a very small metadata index | L1 metadata remains always loaded; not default-zero |
| [fworks-tech/agenthood#614](https://github.com/fworks-tech/agenthood/issues/614) | Proposes lazy loading and on-demand metadata fetch | Feature request only; no coding/non-coding gate |
| [NousResearch/hermes-agent#16493](https://github.com/NousResearch/hermes-agent/issues/16493) | Proposes task-domain bootstrapping and index-first progressive context | Broad agent architecture proposal, not a Codex hook implementation |

## Positioning

This project should be described as:

> The first known public implementation of a binary coding/non-coding metadata gate for Codex skills.

It should **not** be described as the first lazy loader, the first skill router, or the first progressive-disclosure system. Those mechanisms have substantial prior art.

## Why Binary Gating Is Still Useful

Relevance routers try to choose the right skill before the model has enough task context. The binary gate makes a cheaper and more reliable first decision:

- a non-coding session pays zero skill metadata;
- a coding session receives the complete compact catalog;
- the model, not a keyword scorer, chooses the actual skill;
- a sticky state avoids oscillation when the user says "continue" or "fix it".

This is a deliberately narrower V1 hypothesis, not a claim that Top-K routing is unnecessary. Top-K can be layered on later.
