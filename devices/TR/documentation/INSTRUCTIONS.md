# INSTRUCTIONS.md — TR Device

**Version:** 3.0 · **Last updated:** 2026-08-04 (teltonika.py migration)

## Setup

No extra setup beyond the root `../../../documentation/INSTRUCTIONS.md` — this folder's scripts run as ordinary subprocesses of the main app using the same `venv/`. You do need, physically:

- A Teltonika RUTX08 (or compatible RutOS 0.7.22.3+ router).
- A BeagleBone Black reachable at `192.168.7.2`, wired per `resources/images/router.jpg` (shown on the app's Connection page). Configurable via `device_config.json` / `TR_BBB_IP`.
- The firmware binary already present at `devices/TR/RUTX_R_00.07.22.3_WEBUI.bin` and the 94-file `og_configs/`/`og_testfile/` templates intact.

## Tutorial: running one gate

1. From the main app, go to **Program Device**, pick `TR` as the device.
2. Pick the airport `.xlsx` for this deployment, then the gate number.
3. Scan the router's QR code (or type its temp password) and hit **Submit**.
4. Tick every cabling checkbox — they gate the Program button.
5. Hit **Program Device**. Expect roughly 6–8 minutes: config templating is near-instant, firmware install and the two reboots are the bulk of it. Those waits are now driven by the router actually going down and coming back rather than fixed sleeps, so a fast unit finishes sooner than the checklist estimates.
6. **The Status panel on the right ticks through nine milestones** — this is new for TR. Green `PASS`, red `FAIL`, with an elapsed timer on the step in flight. Console output is still there for detail; watch for `Incorrect!` lines, which are the script's own self-checks failing.
7. If programming succeeds, the label is written and the functional test runs (Modbus floodlight toggle, driven from the BeagleBone). If programming *fails*, the run stops there: no label, and the test is skipped — deliberately, since testing a router that did not program only produces a second, more confusing failure.
8. After completion, check the airport `.xlsx`. The gate's row should have a MAC address, a **black** timestamp in `Router Programmed On`, a label file linked in `Label`, and `PRG #` incremented. A **red** timestamp and a `Crash Report` link mean something failed — see `../debugging.md` for prior incidents with similar symptoms.

If a gate has already been programmed, the run ends almost immediately: `check_ip` sees a gate-address lease on the BeagleBone, prints `Router already programmed to IP:...`, marks the remaining milestones `SKIPPED` and exits **successfully**. That is not a failure — there was simply nothing to do.

## Warnings

- **`TR_*` environment variables now affect the whole device.** Both `prog_dev.py` and `teltonika.py` read `device_config.json`, so `TR_BBB_IP`, `TR_ROUTER_TEMP_IP`, `TR_FIRMWARE_FILENAME`, `TR_REBOOT_TIMEOUT` and the rest take effect everywhere. Nothing is hardcoded in the scripts any more. (Older notes describing a half-working override are out of date.)
- **Do not turn `config_manifest.json` into a directory listing.** `og_configs/` holds 94 files but only **82** are pushed; the other 12 (`certificates`, `log`, `speedtest`, `siteman_*`) are per-unit device state that provisioning must leave alone. `tests/test_tr_config_manifest.py` guards this, and fails if a new file appears in `og_configs/` without a deliberate decision about it.
- **Don't hand-edit `configs/` or `testfile/`.** Both are overwritten from `og_configs/`/`og_testfile/` at the start of every run. Edit the `og_` originals.
- **A run now fails loudly if the config template cannot be patched.** If `og_configs/network` ever stops containing the placeholder `10.28.18.2`, staging raises instead of pushing an unpatched config. The old code printed a warning and carried on, which shipped the template's address to the router as if it were the gate's.
- **A missing MAC is survivable, not fatal.** `identity` reports `SKIPPED` and the label's `MA:` field comes out blank; the router itself is fine.
- **`JKC-SLC.xlsx` in this folder is corrupt** — not a valid `.xlsx` file. Selecting it gives an empty Gate dropdown and a printed reason rather than a crash, but it needs replacing from a good copy.

## Future actions

The migration is complete — both files sit on the shared layer. What is left:

- **Replace `JKC-SLC.xlsx`** from a good copy; the file in the repo is not a valid `.xlsx`.
- **Consider resume-on-failure.** `digix20.py` works out where the router currently is and restarts at the right milestone, so a failed attempt does not need a factory reset. TR only has the coarse "already programmed, skip everything" check. This is the largest remaining difference between the two devices.
- **`FloodLighToggle.py` success is a substring match** on `"Bytes in received"`. Parsing the Modbus response properly would give a real pass/fail.

## FAQ

**Q: The router already has an IP other than the template default — what happens?**
A: `check_state` looks for an address matching `TR_BBB_PROGRAMMED_PATTERN` (default `10.x.y.123`) via the BeagleBone and, if it finds one that is not the template address, ends the run successfully without programming. Note the Digi handles this differently — `digix20.py` works out where the router actually is and *resumes* at the right milestone instead of stopping.

**Q: Do `TR_*` environment variables work?**
A: Yes, throughout. Both `prog_dev.py` and `teltonika.py` load `device_config.json` with the `TR_` prefix, so any key in that file can be overridden per machine.

**Q: The run finished in 20 seconds and everything says SKIPPED.**
A: `check_ip` found a gate-address lease on the BeagleBone, meaning this router was already programmed. It exits successfully without touching anything. To reprogram deliberately, factory-reset the router first.

**Q: Where do I look for prior incident history on a weird failure?**
A: `../debugging.md` — a running hand-kept log of specific failure signatures (IP mismatches, firmware update prompts, ping failures) with the previous developer's hypotheses and outcomes.

**Q: Can I safely edit `og_configs/`?**
A: Yes, deliberately — it's the reusable template for every future gate. Never hand-edit `configs/`; it's overwritten from `og_configs/` at the start of every run (`stage_files`, `devices/TR/teltonika.py:219`). If you *add* a file there, decide whether it should be pushed and add it to `config_manifest.json` — `tests/test_tr_config_manifest.py` will fail until you do, on purpose.

**Q: What does `oshkosh_log.xlsx` do?**
A: It's excluded from the airport dropdown by `excel_utils.get_excel_files` and functions as a master deployment log across airports rather than a selectable gate sheet.

**Q: The label came out with a blank `MA:` field.**
A: The MAC was never captured — the `identity` milestone shows `SKIPPED`. `mac_utils.extract_mac` understands several `ifconfig`/`ip link` formats and falls back to `ip link show`, so this now means the router genuinely reported nothing recognisable. The rest of the label is still written, and the sheet keeps any MAC recorded on a previous run for that gate.
