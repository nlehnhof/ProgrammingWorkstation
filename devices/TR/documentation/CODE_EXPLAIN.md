# CODE_EXPLAIN.md — TR Device

**Last commit:** `HEAD` (2026-08-04) — "Migrate teltonika.py onto the shared layer"

## Migration complete

Both files in this folder now sit on `resources/utilities/`. `prog_dev.py` was migrated first (943 → 364 lines); `teltonika.py` followed.

`teltonika.py`'s line count barely moved — 571 → 611 total, and **411 → 403 executable lines** — but that number hides the change. 82 of the old lines were repetitive `sftp.put()` calls that are now one loop over `config_manifest.json`; what replaced them is structure, real error handling and comments explaining the why. It went from a flat run of top-level statements to seven dispatched milestones.

## `teltonika.py` — **Complex** (611 lines, seven milestones)

Runs as a subprocess with `(gate_ip, netmask, gateway, temp_pass)` as `sys.argv`. Configuration is `load_config(DEVICE_DIR, env_prefix="TR_")` (`:55`); transport is `SSHSession`; every wait is completion-driven.

### Structure

`STEPS` (`:571`) dispatches seven functions from `main()`, mirroring `digix20.py`:

| Step id | Function | What it does |
| --- | --- | --- |
| `check_ip` | `check_state` (`:188`) | Reads the BBB's `eth0`. A 10.x.y.123 lease that isn't the template address means this gate is already done. |
| `staging` | `stage_files` (`:219`) | Refreshes `configs/` and `testfile/` from the `og_` originals, points both at this gate, uploads the test script to the BBB. |
| `firmware` | `install_firmware` (`:272`) | SFTPs the firmware, verifies size, runs `sysupgrade`, waits for the router to go down. |
| `reboot_1` | `verify_firmware` (`:340`) | Waits for it back, then confirms the running version. |
| `config_push` | `push_configs` (`:441`) | Pushes the 82 manifest files to `/etc/config/`, stat-verifying each. |
| `identity` | `read_identity` (`:481`) | Reads the MAC via `mac_utils.extract_mac`. |
| `reboot_2` | `final_reboot` (`:518`) | Reboots so the config takes effect, waits for it back. |

`main()` (`:582`) catches `StepError`, emits `FAIL` for the step that was in flight, and returns a non-zero exit code. `AlreadyProgrammed` (`:69`) is caught separately and returns **0** — a gate that was already done is not a failure, which preserves the old `sys.exit(0)`.

### What changed, and why each mattered

- **Connections.** Every operation used to open its own `paramiko.SSHClient`, and shells opened with `invoke_shell()` were never closed. Now one pooled `SSHSession` per phase, with `ManagedShell` for interactive work.
- **`router_session()` (`:151`) replaces `ssh_router_connect(num, admin_num)`.** The old function's nested bare `except:` meant that when *both* connection attempts failed it printed "Errors in Authentication" and returned a client that had never connected — every following step then failed obscurely. `connect_with_fallback` tries the candidate list from `router_candidates()` (`:123`) and raises if none work. The candidate list is also wider: factory address and post-config address, each with the scanned password and the configured one, so a rerun against a partly-configured router finds it.
- **Waits.** Firmware install was a flat `time.sleep(75) + sleep(60) + sleep(60)`; the reboot was `sleep(30) + sleep(60)`. Both were worst-case padding. Now `wait_for_port(up=False)` confirms the box actually went down, then `wait_for_any_port` (`:394`) waits for it back. `wait_for_any_port` shares one deadline across the candidate addresses — the router can return on the factory or the configured address depending on how far the run got, and polling each with a full timeout would treble the failure path.
- **Firmware verification.** The old check was `"07.22" in <login banner>`. Kept, but with a fallback to `cat /etc/version` (`:363`), so a build with a different greeting isn't failed for cosmetic reasons. The expected version is `CONFIG["firmware_version"]`, not a literal.
- **The 82 config files** were 82 hardcoded `sftp.put()` lines. They are now `config_manifest.json`. **This is deliberately not "every file in `configs/`"** — see the manifest's own comment and `tests/test_tr_config_manifest.py`. Each file is now stat-verified after transfer; previously nothing checked that any of them arrived.
- **MAC extraction** used a single `"eth0" ... "HWaddr"` string check that returned nothing whenever busybox changed format. Now `mac_utils.extract_mac(output, interface=...)`, with an `ip link` fallback. A missing MAC reports `SKIPPED`, not `FAIL` — the label field goes blank but the router is fine.
- **A dead `shell.recv()` on a closed channel** sat between the old firmware install and its wait (`shell.close()` at old `:361`, `shell.recv(4096)` at old `:369`). Gone with the restructure.
- **The "revert the network file" step is gone.** It rewrote `configs/network` back to the template address after each run. That was already redundant — the run *starts* by re-copying from `og_configs/` — and `refresh_working_copy` makes it provably so. `configs/network` now keeps the last gate's address, which is more useful when debugging.

### Milestones

The `status` aliases at `:57-62` emit the `##STATUS##` markers `prog_dev.py` forwards to the GUI. With `checklist.json` added, **TR now has the live Status panel** the Digi has had.

## `prog_dev.py` — **Medium** (364 lines)

Unchanged in substance since its own migration; see git history for the three bugs fixed there (the double read of `process.stdout`, testing after a failed program, and the leaked shell channel). Two changes came with the `teltonika.py` work:

- `stage_test_script` (`:344`) now delegates to `templating.stage_template`, the same helper `teltonika.py` uses for `og_configs/`. Its hand-rolled copy-and-regex is gone.
- It reports the `label` and `testing` milestones itself (`:238`, `:282`), because both happen in this process after the hardware script has exited.

## `resources/utilities/templating.py` — **Simple** (shared, new)

`refresh_working_copy(source, dest)` re-copies a template folder; `patch_file(path, old, new)` substitutes and **verifies by counting replacements**; `stage_template(...)` does both.

The verification detail is the point. The old code checked `if new_ip in content` after the substitution — which is satisfied by a file that already contained that address from a previous run. A substitution that silently did nothing still looked like it worked, and the previous gate's configuration went onto this gate's router. Counting replacements catches that; `tests/test_templating.py` pins the behaviour. `patch_file` also matches the placeholder as a whole token, so replacing `10.28.18.2` cannot corrupt a `10.28.18.20` elsewhere in the file.

## `FloodLighToggle.py` — **Medium** (558 lines, third-party-derived)

A Modbus/TCP client (attributed to Andy Cranston / Cranston Innovation in its header, `:3`) adapted as the post-programming functional test. Both `teltonika.py` and `prog_dev.py` point its hardcoded `127.0.0.1` at the gate's real address before copying it to the BeagleBone. Success is detected by string-matching `"Bytes in received"` in the BBB's output — there is no structured parsing of the Modbus response.

## Non-code assets

- `config_manifest.json` — the 82 files pushed to `/etc/config/`, in order, extracted verbatim from the `sftp.put()` calls it replaced. The 12 files in `og_configs/` it omits (`certificates`, `log`, `speedtest`, and the `siteman_*` group) are per-unit device state that provisioning must leave alone.
- `checklist.json` — the nine Status-panel rows. Seven come from `teltonika.py`; `label` and `testing` are reported by `prog_dev.py`.
- `device_config.json` — **read by both files now.** Carries the BBB and router addresses, credentials, firmware filename and version, and every timeout. All overridable with `TR_*` environment variables.
- `og_configs/` / `configs/` (94 files each) — see `WORKFLOW.md` §3. Never edit `og_configs/`.
- `og_testfile/` / `testfile/` — same pattern, for `FloodLighToggle.py`.
- `*.xlsx` — per-airport gate data. `oshkosh_log.xlsx` is excluded from the dropdown and acts as a master log. **`JKC-SLC.xlsx` is corrupt** — not a valid `.xlsx`. It is skipped gracefully but needs replacing from a good copy.
- `labels/`, `router_labels/` — `router_labels/` is where labels are written; a Brady printer watches it and moves printed files to `labels/`.
- `history/` — abandoned prior implementations, reference only.
