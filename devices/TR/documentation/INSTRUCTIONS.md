# INSTRUCTIONS.md — TR Device

**Version:** 2.0 · **Last updated:** 2026-08-04 (`e96074a`)

## Setup

No extra setup beyond the root `../../../documentation/INSTRUCTIONS.md` — this folder's scripts run as ordinary subprocesses of the main app using the same `venv/`. You do need, physically:

- A Teltonika RUTX08 (or compatible RutOS 0.7.22.3+ router).
- A BeagleBone Black reachable at `192.168.7.2`, wired per `resources/images/router.jpg` (shown on the app's Connection page). That address is now configurable — see Warnings.
- The firmware binary already present at `devices/TR/RUTX_R_00.07.22.3_WEBUI.bin` and the 94-file `og_configs/`/`og_testfile/` templates intact.

## Tutorial: running one gate

1. From the main app, go to **Program Device**, pick `TR` as the device.
2. Pick the airport `.xlsx` for this deployment, then the gate number.
3. Scan the router's QR code (or type its temp password) and hit **Submit**.
4. Tick every cabling checkbox — they gate the Program button.
5. Hit **Program Device**. Expect roughly 7–8 minutes total: config templating is near-instant, firmware install/boot is the bulk of the wait (~3.5 min install + ~1.5 min reboot, both still fixed `time.sleep()` calls inside `teltonika.py`).
6. Watch console output for `Incorrect!` lines — those are the script's own self-checks failing, and each corresponds to a step in `WORKFLOW.md` §2.
7. If programming succeeds, the functional test runs next (Modbus floodlight toggle, driven from the BeagleBone). If programming *fails*, the run stops there and the test is skipped — that is deliberate; testing a router that did not program only produces a second, more confusing failure.
8. After completion, check the airport `.xlsx`. The gate's row should have a MAC address, a **black** timestamp in `Router Programmed On`, a label file linked in `Label`, and `PRG #` incremented. A **red** timestamp and a `Crash Report` link mean something failed — see `../debugging.md` for prior incidents with similar symptoms.

TR ships no `checklist.json`, so the app's live Status panel stays empty for this device. Progress is the console output. Adding the panel is the last step of the migration in `CODE_EXPLAIN.md`.

## Warnings

- **`teltonika.py` still hardcodes its addresses and credentials.** `prog_dev.py` now reads `device_config.json` and honours `TR_*` environment variables, so `TR_BBB_IP`, `TR_BBB_PASSWORD` and `TR_TEST_SCRIPT_TIMEOUT` affect the orchestration and functional-test layers. They do **not** reach inside `teltonika.py`, which carries its own copies of the BBB address, the router IPs and the passwords (`CODE_EXPLAIN.md` lists the lines). If a config override half-works, that split is why.
- **Don't hand-edit `configs/` or `testfile/`.** Both are overwritten from `og_configs/`/`og_testfile/` at the start of every run. Edit the `og_` originals.
- **`ssh_router_connect`'s fallback logic swallows connection errors silently** (bare `except:` at `devices/TR/teltonika.py:120-126`). A router that fails to respond on both the temp and fallback IP prints "Errors in Authentication" and carries on executing subsequent steps rather than aborting cleanly. This is inside `teltonika.py` and was not part of the `prog_dev.py` migration.
- **`teltonika.py`'s MAC extraction only understands old `HWaddr`-style `ifconfig` output.** A firmware update that changes busybox's formatting will make it silently return nothing — the label's `MA:` field then comes out blank. `resources/utilities/mac_utils.extract_mac` handles several formats and is what should replace it.
- **`JKC-SLC.xlsx` in this folder is corrupt** — not a valid `.xlsx` file. Selecting it gives an empty Gate dropdown and a printed reason rather than a crash, but it needs replacing from a good copy.

## Future actions

Everything below is about `teltonika.py`; `prog_dev.py` is done.

1. Replace the paramiko helpers with `resources/utilities/ssh_session.SSHSession` / `ManagedShell` — one pooled connection, enforced timeouts, and channels that always close.
2. Replace the fixed `time.sleep()` waits with `wait_utils.wait_for_port` / `wait_for_ssh` / `run_cli`, so a step is confirmed by an observed event rather than a guess at how long it takes. The ~3.5 min and ~1.5 min sleeps are both worst-case padding.
3. Read configuration through `device_config.load_config(DEVICE_DIR, env_prefix="TR_")`, as `prog_dev.py:160` already does, and delete the hardcoded constants.
4. Swap the MAC parser for `mac_utils.extract_mac(text, interface="eth0")`.
5. Add `status.running(...)` / `passed(...)` / `failed(...)` calls and a `checklist.json`, and TR gets the same live Status panel the Digi has.

`devices/digiIX20/digix20.py` has been through exactly this and is the reference.

## FAQ

**Q: The router already has an IP other than the template default — what happens?**
A: `teltonika.py:194-201` checks for an address matching `10.\d+\.\d+\.123` via the BBB and exits immediately (`sys.exit(0)`) without programming if found, printing `"Router already programmed to IP:{addr}"`. Note the Digi handles this case very differently — `digix20.py` detects where the router actually is and *resumes* at the right milestone instead of refusing.

**Q: I set `TR_BBB_IP` and it half-worked. Why?**
A: `prog_dev.py` reads it; `teltonika.py` does not. See Warnings.

**Q: Where do I look for prior incident history on a weird failure?**
A: `../debugging.md` — a running hand-kept log of specific failure signatures (IP mismatches, firmware update prompts, ping failures) with the previous developer's hypotheses and outcomes.

**Q: Can I safely edit `og_configs/`?**
A: Yes, deliberately — it's the reusable template for every future gate. Never hand-edit `configs/`; it's overwritten from `og_configs/` at the start of every run (`devices/TR/teltonika.py:229-234`).

**Q: What does `oshkosh_log.xlsx` do?**
A: It's excluded from the airport dropdown by `excel_utils.get_excel_files` and functions as a master deployment log across airports rather than a selectable gate sheet.

**Q: The label came out with a blank `MA:` field.**
A: The MAC was never captured. Either `teltonika.py`'s single-format parser didn't recognise the `ifconfig` output (see Warnings), or the router never got that far. The rest of the label is still written, and the sheet keeps any MAC recorded on a previous run for that gate.
