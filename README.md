# getonmylevel

**A small set of skills and one hook for Codex, Claude Code, GitHub Copilot CLI and VS Code, and OpenCode. The agent works directly, loads a skill only when it reaches the step that skill covers, and checks its work by running the project's own tests.**

There are three skills, each a short procedure for a step agents often skip or get wrong:

| Skill | When the agent reads it | What it does |
| --- | --- | --- |
| [verify](skills/getonmylevel-verify/SKILL.md) | Before reporting a code change as done, and when fixing a bug | Finds and runs the repository's own tests, typecheck, and build for the changed files (with a bundled `find_checks.py`). For a bug: reproduce it through the project's entry point, fix it, rerun the same command. |
| [ui-check](skills/getonmylevel-ui-check/SKILL.md) | After changing an interface that renders | Renders the screen at 375, 768, and 1280 px, carries out the requested flow, and checks for concrete defects (with an optional Playwright `screenshot.py`). |
| [context](skills/getonmylevel-context/SKILL.md) | Cross-package callers, or an API whose behavior depends on the installed version | Uses an existing code index if there is one, and reads the installed version's own docs and types. |

Optional extras: a **stop hook** for each client that runs the targeted checks when the agent finishes and returns failures to it, and a **reviewer** role that re-checks risky changes in a fresh context by running the checks.

## What changed from earlier versions

Earlier versions added everything that seemed helpful. This version keeps a part only if a controlled evaluation showed that kind of change improves coding agents. Everything else was removed, including parts that cost tokens or questions without a measured benefit.

| Part | Earlier versions | Now | Evidence |
| --- | --- | --- | --- |
| Skills | 7 broad guidance skills, all read at the start of every conversation | 3 short procedures, each read only when its step comes up | Broad public skills showed no effect on average, and forced skills raised tokens by 72–394% and lowered success. Narrow, curated procedures raised resolution from 33.9% to 50.5%. |
| Workflow question | "Simple or Agentic?" asked before every edit | Removed; the agent works directly | No study shows a benefit. It stops headless runs and adds a turn to every task. |
| Checking work | Roles told not to run checks unless asked | verify runs the project's own nearby tests; for a bug it reproduces, fixes, and reruns | Running the right existing tests cut silent regressions from 18.8% to 4.8%. Writing a failing test first, or self-review without running anything, did not help. |
| Stop hook | None | Optional for all four clients: failing checks go back to the agent | Harness checks, such as a check before finishing, moved one model from 52.8% to 66.5%. A guard rejecting syntax errors raised the solve rate from 15.0% to 18.0%. |
| Agent roles | designer → implementer split, plus reviewer and tester | One agent by default; one optional reviewer that runs checks | Multi-agent designs used 1.4–4.7 times the tokens without reliable gains on code. Independent patch verification gained 3.6–7.0 points. |
| CodeGraph | Offered on every task, and set up by the installer | Removed | An indexing prompt on every task has no evidence, and the CodeGraph setup itself had mixed results: 55% fewer tool calls but 6.8% higher cost in one test. |
| Suggested add-ons | RTK, Impeccable, UI UX Pro Max, Anti UI Slop, Last 30 Days, CLI-Anything | Two Go skills (spf13/viper, stretchr/testify) | The two Go skills are 2 of the 4 out of 98 public skills with a significant gain in SWE-Skills-Bench. RTK's independent benchmark found no cost saving; the others had no controlled evaluation. |

One limit applies: the evidence is for each *kind* of change, measured by other people on their own models and tools. This exact bundle has not yet been measured head to head against the previous one; see [Why it is built this way](#why-it-is-built-this-way).

## Get started

### GUI

Requirements: Git, Python 3.11 or newer, Tkinter, and a graphical display. The setup tools use only Python's standard library.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
python tools/install_gui.py
```

Choose a client, select skills and a scope, then review and confirm. Choose an existing repository for repository scope. Skill files come from the checkout you cloned. **Active by default** adds a short index of the selected skills to the client's instructions; review and confirm that change separately. The optional **Agents** tab configures the reviewer role.

### Headless

Requirements: Git and Python 3.11 or newer. No Tkinter or graphical display is needed.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
python tools/install.py install --client claude --scope user
python tools/install.py activate --client claude --scope user --skills all
python tools/setup.py hooks install --client claude --dry-run   # optional; then run again with --yes
```

Use `--client codex`, `--client copilot`, or `--client opencode` for the other clients, including the hook. See [scriptable installation](INSTALL.md#scriptable-installation) for selection, scope, updates, and removal.

## Upgrading from the seven-skill release

Run `install` or `update` again for each client and scope you used. It replaces the old managed block with the new one, keeping your own text and line endings, and moves the six retired skills to `getonmylevel-backups`. The old Simple-or-Agentic question, the start-of-conversation reads, and the CodeGraph offer stop with that. Details, including the name mapping, how to remove the retired roles, and how to remove a CodeGraph setup an earlier release made, are in [INSTALL.md](INSTALL.md#upgrading-from-the-seven-skill-release).

## What activation writes

Clients find installed skills on their own by matching each skill's description, but they often miss one: in Vercel's Next.js evaluation an available skill went unused in 56% of cases. **Active by default** therefore adds one line per selected skill to the client's instruction file, naming the step where it applies:

```text
<!-- getonmylevel-skills:begin -->
## getonmylevel skills

These installed skills are procedures for specific steps. Read a skill when you reach its step:
- `~/.claude/skills/getonmylevel-verify/SKILL.md`: before finishing a code change, and when fixing a bug
- `~/.claude/skills/getonmylevel-ui-check/SKILL.md`: after changing an interface that renders in a browser or app window
- `~/.claude/skills/getonmylevel-context/SKILL.md`: when finding callers across packages, or using an API that depends on the installed version
<!-- getonmylevel-skills:end -->
```

That is about 70 words, the same in every session so prompt caches stay warm. Skill bodies, about 1,000 words together, load only when a step comes up. The previous block was 428 words. It told the client to read 2,938 more words of skill instructions at the start of every conversation and to ask a workflow question before every edit. Instructions in natural language cannot intercept client tool calls or guarantee that a skill is read; the hook is the part that runs whether or not the agent remembers.

## Why it is built this way

The design follows controlled evaluations of coding agents. Most are 2026 preprints, and some have revised their figures between versions.

- **Broad guidance costs tokens and rarely helps.** Across 98 public skills in 3,920 paired runs, the share of checks passed moved from 76.59% to 76.93%; 4 skills helped, 2 hurt ([SWE-Skills-Bench](https://arxiv.org/abs/2603.15401)). Forcing relevant-looking skills into the prompt raised tokens by 72–394% and lowered success by 1.3–4.2 points, most on easy tasks ([WebDev-Skills-Bench](https://arxiv.org/abs/2608.23067)). Generated repository instructions raised cost by about 20% without a significant gain ([Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988)). This is why the communication, engineering, practices, simplicity, and discovery skills are gone.
- **Narrow, curated procedures help.** Curated skills matched to the task raised resolution from 33.9% to 50.5%. One to three skills beat four or more, and comprehensive skills gained almost nothing ([SkillsBench](https://arxiv.org/abs/2602.12670)). Helpful skills supply a step the agent would otherwise skip, state exact requirements and short "don't" rules, ship scripts, and say when they do not apply. Each skill here follows that pattern.
- **Running the right existing tests helps; ritual does not.** Running the issue's target tests cut silent regressions from 18.8% to 4.8%. Telling the agent to write a failing test first changed neither resolve nor regression rate (Silent Regressions, NeurIPS 2026). Validating candidate fixes with regression and reproduction tests raised correct selections from 77 to 96 of 300 ([Agentless](https://arxiv.org/abs/2407.01489)). Self-review passes without execution feedback lowered the resolve rate. The verify skill therefore runs the project's checks and reproduces bugs instead of asking for self-audit or new test files.
- **Harness feedback beats prose.** Changing only the harness (a check before finishing, loop detection, and others) moved one model from 52.8% to 66.5% on Terminal Bench 2.0 (LangChain). The Stop hook is that kind of check, with a loop guard.
- **Multiple agents cost more without reliably helping on code.** Coordinated designs used 1.4–4.7 times the tokens and 2.6–5.8 times the latency, and five of six multi-agent workflows scored below a single agent in another study ([arXiv 2611.12953](https://arxiv.org/abs/2611.12953), [arXiv 2606.05670](https://arxiv.org/abs/2606.05670)). On 133 small programming problems, one agent was accepted 98.50% of the time and four roles 97.74%, at about four times the generation time. One agent is the default; the reviewer is opt-in.
- **Rendered feedback improves interfaces.** Screenshot feedback raised appearance scores from 3.0 to 3.6, and GUI interaction feedback then raised functional accuracy from 46.6% to 49.9% (WebGen-Agent). The ui-check skill renders the screen and uses it.

These results come from other people's benchmarks, models, and harnesses, and skill effects transfer poorly between them: 40 of 98 skills changed sign between Codex and Claude Code. This bundle has not yet been measured head to head against the previous one. The intended comparison runs a verified clean baseline, the old bundle, this one, each skill alone, and a length-matched irrelevant skill, with hidden acceptance tests, easy tasks included, and cost, turns, questions asked, and latency recorded.

## Supported clients

| Capability | Codex | Claude Code | GitHub Copilot CLI and VS Code | OpenCode |
| --- | --- | --- | --- | --- |
| Bundled skills and managed instructions | Yes | Yes | Yes | Yes; repository `AGENTS.md` block shared with Codex |
| Optional reviewer role | TOML | Markdown subagent | `.agent.md` profile | Markdown subagent (`mode: subagent`) |
| Verify stop hook | `Stop` in `hooks.json` (trust with `/hooks`) | `Stop` in `settings.json` | `agentStop` in `~/.copilot/hooks` | V2 plugin (not yet run in a live client) |
| Role model settings | Model and effort | Model and effort | Model only; no reasoning effort | Model only (`provider/model-id`, optional `#variant`); no separate effort |
| Suggested items | Go viper and testify skills | Same | Same | Same |

See [client capabilities and paths](INSTALL.md#client-capabilities-and-paths) for destinations and scope behavior. All four support the bundled skills, the reviewer role, the stop hook, and the suggested items; formats differ as shown above.

## Optional integrations

Suggested add-ons follow the same rule as the rest of the bundle: each is kept only with a controlled evaluation showing a benefit, and the evidence is shown next to it. Only the two Go skills that SWE-Skills-Bench found significantly helpful (spf13/viper and stretchr/testify) qualify, and only in Go projects that use those libraries. Retired add-ons can still be removed. See [suggested skillsets and tools](INSTALL.md#suggested-skillsets-and-tools) for the evidence and pins.

## More information

[INSTALL.md](INSTALL.md) covers prerequisites, destinations, activation, upgrading, the verify hook, update and removal, troubleshooting, headless setup, and integrations. [ATTRIBUTION.md](ATTRIBUTION.md) lists sources and the projects that informed earlier releases.

## License

Source-available under a custom license. Personal, noncommercial use and private modifications are permitted. Commercial use and public distribution of modified or derivative work require prior written permission. This is not an open-source license. See [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md).
