# Mailbox / Watcher Tools

These scripts are a public, sanitized reference implementation of the mailbox-backed
LLM audit path used by the paper's overseer experiments.

Included tools:

- `llm_danse2_watcher.py` — polls a mailbox endpoint, runs local CLI-backed LLMs,
  and posts suggestions or overseer decisions back to the mailbox
- `llm_mailbox_client.py` — minimal helper for checking mailbox status, posting
  prompts, and retrieving suggestions
- `llm_audit_mailbox_runner.py` — local watcher used for the audit-ablation batches

Scope:

- These scripts demonstrate one operational pattern for the bounded audit interface.
- The scientific results do not depend on this exact transport layer; equivalent
  direct-API or alternative service-mediated implementations are possible.

Configuration:

- Provide the mailbox endpoint explicitly with `--mailbox-url`.
- Provide the mailbox token explicitly with `--token` or `--mailbox-token`.
- Install any local LLM CLIs you intend to use and ensure they are on your `PATH`.
- `llm_danse2_watcher.py` defaults to `gpt-5.2-codex` for Codex runs and uses
  the provider CLI defaults unless overridden externally.

Operational notes:

- The example URLs in docstrings use placeholder endpoints such as
  `https://example.org/tasai_mailbox`.
- Site-specific wrappers, shell aliases, or scheduler glue should be kept outside
  these scripts so the public copy remains generic.
