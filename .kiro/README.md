# .kiro — the spec-driven record of Séance

Kiroween requires this folder at the repository root, and it must not be listed in
`.gitignore`. It holds the specs the project was built from, in the order they were written,
and the custom agents that reviewed it.

## Specs

| file | what it fixed | status |
|---|---|---|
| `specs/01-problem.md` | the problem and what already exists | written first, still accurate |
| `specs/02-scope.md` | what the prototype must and must not do | honoured; the out-of-scope list was never crossed |
| `specs/03-rule-sweep-bos.md` | the trading rule in words, before any code | encoded in `skeletons/sweep_bos.json`, unchanged since |
| `specs/04-probe-variant.md` | generating the Pine probe instead of hand-editing it | **specified, not implemented** |

Spec 04 is deliberately left in place. It is the next piece of work, written to the same
standard as the three that were built, and the README says in plain words that the Pine
comparison still rests on a hand-edited probe until it is done.

## Custom agents

Three read-only reviewers (`agents/*.json`), each with `fs_read` only — no write tool, no
shell, so none of them could change what it was reviewing:

- **`seance-spec-auditor`** — architect and spec engineer; reviews the architecture and the
  specs and proposes one substantive change at a time.
- **`seance-qa`** — independent cross-platform QA; audits the code as someone who did not
  write it and owes its author no agreement.
- **`seance-ux`** — product reviewer; designs the shortest complete journey for a developer
  opening the repository for the first time.

The QA agent is what turned the verification from decoration into a real check: the
`verify/SABOTAGE_RUN` evidence (an older generator scored **REJECTED 7/9**, naming five
predicates as dead text) exists because the audit insisted the acceptance test must be able
to fail before its passing result means anything.
