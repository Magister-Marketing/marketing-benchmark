# Contributing

Contributions are welcome, through pull requests in this repository. By
contributing you agree that your contribution is released under the
repository's [MIT License](LICENSE). Report security problems privately, as
[SECURITY.md](SECURITY.md) describes, never in an issue.

Before opening a change:

1. Keep provider-specific or company-private behavior in a downstream plugin.
2. Use invented or redistribution-approved fixtures only.
3. Add deterministic tests for new schemas, adapters, environments, scorers, or
   validators.
4. Run `make check` without provider credentials or paid model calls.
5. Document any compatibility change to a manifest or plugin contract.
6. Keep the docs in step with the change. A task added, changed, or moved on
   or off the board goes into `eval_runner/board.json` (checked by
   `tests/test_board.py`), `docs/TASKS.md` and `CHANGELOG.md` together. A
   change to how answers are checked or counted goes into `docs/SCORING.md`.
