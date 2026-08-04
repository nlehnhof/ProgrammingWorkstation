# WORKFLOW.md — TR Device

**Last commit:** `e96074a` (2026-08-04) — "Simplify onto a shared utility layer; delete dead abstractions"

## Recent changes (`e96074a`)

- **`prog_dev.py` was rewritten** onto the shared utility layer (943 → 361 lines). The Excel/crash-log/label handling described in §4 is no longer written out here at all — it is `resources/utilities/reporting.py`.
- **Three bugs went with it**: the double read of `process.stdout` (§1), the functional test running after a failed program (§1), and a leaked shell channel per `ssh_run_shell` call.
- **`teltonika.py` is unchanged.** §2 and §3 below still describe it accurately.

## 1. The two-process pipeline

`pages/program_page.py` `exec()`-loads `devices/TR/prog_dev.py` and calls `run_main_script(airport, gate, temp_pass, device)` (`devices/TR/prog_dev.py:199`). That function does **not** talk to hardware itself — it looks the gate up in Excel, launches `teltonika.py` as a separate child process, then runs the functional test and records the outcome.

```mermaid
sequenceDiagram
    participant PP as ProgramPage (exec'd prog_dev.py)
    participant TK as teltonika.py (subprocess)
    participant BBB as BeagleBone Black
    participant RTR as Router

    PP->>PP: lookup_excel(sheet, gate, device) — by header name; sets globals + valid_ip
    PP->>TK: status.watch_process(script_command(teltonika.py, ip, mask, gw, pass))
    TK->>BBB: SSH — check if router already programmed (ip addr show eth0)
    TK->>RTR: SSH (temp creds) — copy config templates, patch WAN IP
    TK->>BBB: SFTP — upload patched FloodLighToggle.py
    TK->>RTR: SFTP — upload firmware .bin, sysupgrade, wait ~3.5 min
    TK->>RTR: SSH (temp creds again) — verify firmware banner, push 94 config files
    TK->>RTR: shell — ifconfig -a, extract MAC
    TK->>RTR: reboot; revert local configs/network back to template IP
    TK-->>PP: stdout stream — consumed in ONE pass
    PP->>PP: reporting.record_result() — crash log, sheet stamp, label
    PP->>PP: run_test_script() — functional test via BBB (only if programming passed)
    PP->>PP: reporting.record_test_result()
```

Two ordering changes are load-bearing:

- **The child's stdout is read exactly once.** The old code looped over `process.stdout`, then looped again; the first loop drained the pipe, so the second — holding all the failure detection, MAC capture and crash logging — iterated an exhausted stream. Every run looked like a success. `status.watch_process` (`resources/utilities/status.py:127`) is now the single pass, shared with the Digi.
- **The functional test runs only after a successful program.** It used to run unconditionally, and before the (dead) error-handling loop, so a router that failed to program was then tested and failed again, more confusingly.

`teltonika.py` reads its four arguments as `sys.argv[1:5]` (`devices/TR/teltonika.py:19-23`) and exits immediately if launched with none. The command is built by `app_paths.script_command()` rather than `[sys.executable, ...]`, because in a packaged build `sys.executable` is the app itself.

## 2. `teltonika.py`'s 9 steps (as coded — unchanged)

```mermaid
flowchart TD
    S0["Check if router already programmed\n(ip addr show eth0 via BBB, lines 188-201)"] --> S1
    S1["Connect to router (temp creds)\n(line 213)"] --> S2
    S2["Copy og_configs/ -> configs/, patch WAN IP\n(lines 217-262)"] --> S3
    S3["Copy og_testfile/ -> testfile/, patch FloodLighToggle.py, upload to BBB\n(lines 264-323)"] --> S4
    S4["Upload firmware .bin to /tmp on router\n(lines 325-360)"] --> S5
    S5["sysupgrade; wait ~3.5 min\n(lines 362-381)"] --> S6
    S6["Reconnect, verify firmware banner shows 07.22\n(lines 383-395)"] --> S7
    S7["Upload 94 config files to /etc/config/\n(lines 397-495)"] --> S8
    S8["Extract MAC via ifconfig -a\n(lines 497-520)"] --> S9
    S9["Reboot; revert configs/network to template IP; wait ~1.5 min\n(lines 522-570)"]
```

Every step prints a verification message. Two output conventions are what `prog_dev.py` reacts to, and they are now defined once, in `resources/utilities/status.py`:

| Convention | Meaning |
| --- | --- |
| `Incorrect! ...` | This step failed. Sets the run's failure flag and becomes the crash-log detail. |
| `MAC Addr: xx:xx:...` | The device's MAC, written into the sheet and onto the label. |
| `Traceback` | An unhandled exception; also marks the run failed. |

A non-zero exit code from the child marks the run failed regardless of what it printed.

`teltonika.py` emits **no** `##STATUS##` milestone markers and TR ships no `checklist.json`, so the Status panel stays empty for this device. Adding both is the last step of the migration described in `CODE_EXPLAIN.md`.

## 3. Config file lifecycle (unchanged)

```mermaid
flowchart LR
    OGC["og_configs/ (94 files, template — never modified)"] -->|copy| CFG["configs/ (working copy)"]
    CFG -->|patch WAN IP for this gate| CFG
    CFG -->|SFTP upload each file| ROUTER["/etc/config/* on router"]
    CFG -->|revert WAN IP to template value after reboot| CFG

    OGT["og_testfile/FloodLighToggle.py (original, never modified)"] -->|copy| TF["testfile/FloodLighToggle.py"]
    TF -->|patch gateway IP| TF
    TF -->|SFTP upload| BBB["/home/raj/FloodLighToggle.py on BBB"]
```

This copy-then-patch-then-revert pattern exists so the same templates can be reused for the next gate without re-cloning from a pristine backup. `configs/network`'s WAN IP is patched to the gate's real IP for the duration of the SFTP push, then reverted to the placeholder (`10.28.18.2`) once the router has rebooted (`devices/TR/teltonika.py:529-548`).

`prog_dev.py`'s `stage_test_script` (`:327`) does the `og_testfile/` half of this, and verifies the substitution actually landed before uploading.

## 4. Excel, crash-log and label output

**This no longer lives in `prog_dev.py`.** All of it is `resources/utilities/reporting.py`, shared with the Digi. `prog_dev.py` supplies the outcome and calls two functions.

```mermaid
flowchart TD
    W["status.watch_process() -> {failed, detail, mac, log}"] --> C{failed?}
    C -->|yes| CL["reporting.write_crash_log() -> crash_logs/"]
    C -->|no| SK["no crash log"]
    CL --> RR["reporting.record_result()"]
    SK --> RR
    RR --> ST["row: MAC, timestamp (red if failed), crash link, PRG #"]
    RR --> LB{failed?}
    LB -->|no| L["label file + hyperlink; then run_test_script()"]
    LB -->|yes| NL["no label; raise, run stops here"]
    L --> T["reporting.record_test_result(): tested-on, test crash link, Test #"]
```

Which cell gets written is decided by **header name**, through `reporting.COLUMNS`:

| Logical field | Header in the sheet |
| --- | --- |
| `mac` | `MAC Address` |
| `programmed_on` | `Router Programmed On` |
| `label` | `Label` |
| `crash_report` | `Crash Report` (1st occurrence) |
| `prg_count` | `PRG #` |
| `tested_on` | `Router Tested On` |
| `test_crash_report` | `Crash Report` (2nd occurrence) |
| `test_count` | `Test #` |

The old code addressed these as `column=7`, `column=8`, … `column=14`, hardcoded at each of four separate copies of the write logic. Reordering a spreadsheet template silently wrote to the wrong cells; now it cannot.

Two conventions `reporting` enforces:

- The `Router Programmed On` timestamp is **red on failure, black on success** — how an operator scanning the sheet spots a gate that needs redoing.
- **A failed run writes no label.** A printable label for a router that did not program is worse than none, because somebody can stick it on.
