# Local project summary

Use a summary only when recurring navigation makes its maintenance worthwhile. Keep it outside source control where practical, and never put secrets or source copies in it.

## Location and initialization

Use an existing project-authorized local location. A path such as `.getonmylevel/context/` is suitable only after confirming it is already excluded from version control. Do not change ignore rules or global configuration silently. If no approved, ignored writable location exists, do not create a summary; explain the prerequisite and ask for an approved location or an ignore-rule change.

Initialize selectively: use ignore-aware tools to identify eligible source, inspect representative authoritative files, and record the scope. Avoid attempting to map every file. A practical layout is:

- `index.md`: purpose, update date, scope, links to topic files, and known stale areas.
- One Markdown file per meaningful subsystem, with compact records for source path, key symbols, responsibility, relationships by path or symbol, last-reviewed commit or date, and uncertainty.

## Query

Read `index.md` first, then search only relevant topic files with `rg`. Follow paths to source and inspect that source before consequential decisions. Treat summary statements as leads, not evidence of current behavior.

## Refresh and stale information

After a material architecture, responsibility, symbol, or relationship change, update affected records only. Add new paths and relationships, update renamed paths, and remove or explicitly mark deleted references. Compare recorded commit/date with relevant changed paths, verify referenced files, and explicitly flag unreviewed or ambiguous details. Git history is a useful aid but cannot prove freshness, especially with uncommitted changes or outside Git. Do not silently infer relationships.

If safe maintenance is not possible, mark affected records stale where practical and report why. Disable summary use by stopping maintenance. Remove the summary directory only at the user's request. Leave existing project and third-party indexes untouched.
