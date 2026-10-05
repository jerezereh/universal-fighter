# Project working instructions

Follow `handoff_doc.txt` and `docs/WORK_PLAN.md`. Read the pinned IKEMEN implementation
before changing runtime boundaries. Keep verified results separate from proposed behavior
and pending interactive validation.

Use Ponytail (full intensity by default) for coding, fixes, architecture and dependency
choices. Use the relevant Universal Modder skills for installed-game reconnaissance,
reverse engineering, file formats, asset conversion and game validation. Read each
applicable SKILL.md before applying its workflow. Both are installed in the user's
Codex skills folder; the pinned Universal Modder reference in
`tools/references/universal-modder` is also available via `tools/bootstrap.ps1`.
Keep Universal Modder as development tooling, never a shipped runtime dependency.

The user authorized committing and pushing throughout the work plan on 2026-10-05.
After each completed, validated work package or coherent implementation step:

1. Update the project progress record with changes, verification and remaining limitations.
2. Inspect the diff and stage only files belonging to that step.
3. Make a descriptive commit and push to the configured remote and current working branch.
4. Report the commit and any failed validation or push. Do not force-push or discard
   unrelated work to resolve a remote conflict.

Do not commit local toolchains, build outputs, runtime saves, extracted assets or the
ignored upstream working copies. Host source changes must be captured in versioned
patches or a maintained fork before committing a step that depends on them.

Do not edit a script while it is running. Validate setup scripts with PowerShell/Bash
syntax checks and exercise changed behavior where practical. Native smoke tests verify
match lifecycle; visual presentation and human controls require interactive validation.
