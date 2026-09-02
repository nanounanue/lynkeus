# 0001 — The TUI shell is a shared package, not a vendored copy

**Status:** Accepted
**Date:** 2026-09-02
**Deciders:** Adolfo De Unánue

## Context

Five projects (corredor, triage-pg, featurizer, meio-sim, acervo) each get a
Textual TUI with the same six standard screens, keys and theme. The shell
could live once, in its own package pinned by every consumer, or be copied
into each repository. The workspace already carries evidence for what copying
does: the two Astro docs sites diverged in framework versions within months of
the second copy.

## Decision

The shell lives in this package, public on GitHub and pinned by git tag, the
way triage-pg already pins featurizer. We create it on day one, and it only
ever holds what the current consumers need. The API stays at 0.x until the third
consumer lands, then 1.0 freezes it.

## Consequences

One fix lands in five places, and consistency is enforced by construction
instead of discipline. The costs are release choreography (a tag plus a bump
per consumer) and one Python floor for everyone, 3.12; featurizer keeps its
3.10 library floor by putting its TUI extra behind a version marker. The shell
never imports project code and never mentions a project name; projects
register adapters and screens into it.
