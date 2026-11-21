# getonmylevel

**Practical Codex skills and agent roles, installed from one small desktop app.**

[Skills](#skills) · [Install](#install) · [License](#license)

## Skills

Six optional skills for communication, context, engineering, interface design, software practices, and skill discovery. Add the designer, implementer, reviewer, and tester agent roles when you need them.

## Install

Requires Python 3.11+ with Tkinter. Clone the repo, then run:

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
python tools/install_gui.py
```

The app has **Skills & installation** and **Agents** tabs. Choose a user or repository scope, review the preview, and confirm changes. Run `python tools/agents_gui.py` to open the same app directly on the existing command path.

Skill installation copies the checked-out files and adds managed default-use guidance to the applicable `AGENTS.md`. Agent setup writes selected role templates. Both tools show planned changes before applying them. The full install behavior, destinations, backups, optional tools, and terminal fallback are in [INSTALL.md](INSTALL.md).

## License

Source-available under a custom license. Personal, noncommercial use and private modifications are permitted. Commercial use and public distribution of modified or derivative work require prior written permission. See [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md).
