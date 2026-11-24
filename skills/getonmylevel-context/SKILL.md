---
name: getonmylevel-context
description: Navigates code where plain search is unreliable, such as finding every caller of a symbol across packages, and checks the installed version of a dependency before relying on its API. Use when a change touches shared behavior used in several packages, or when an API's behavior depends on the installed version. Not needed for small, local edits.
---

# Hard navigation and version-specific APIs

## Callers across packages

1. If the session already has a code index (a language server, an IDE index, or a code-search tool), ask it for references to the symbol.
2. Otherwise search for the symbol name, including re-exports, aliases, string-based lookups (registries, dependency injection, reflection), and generated code.
3. Open each call site before changing the shared behavior. Treat index results as leads: confirm them in the source.

Don't create or initialize an index, and don't offer one, unless the user asks.

## Version-specific APIs

1. Read the installed version from the lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`, `uv.lock`, `Cargo.lock`, `go.sum`) or the environment, not from memory.
2. Read the documentation or type definitions that ship with that version: `node_modules/<pkg>`, the package's `.d.ts` files, `site-packages/<pkg>`, or docs in the repository. Use a version-matched web page only if nothing local exists.
3. If the API you planned to use is not in that version, say so and use what the installed version provides.

Don't upgrade a dependency to get a newer API unless the user asks.
