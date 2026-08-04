# Programming Workstation — Cheat Sheet

*One page. Plain language. No code.*
*Current as of `e96074a`, 2026-08-04.*

---

## What problem does this solve?

Airport jet bridges have a small router in them that controls the gate equipment. Before a router can be installed, somebody has to set it up: load the right software onto it, give it the right network address for that specific gate, test that it works, and print a label for it.

Doing that by hand takes about **30 minutes per router** and is easy to get wrong. There are hundreds of gates.

**This app does it in about 7 minutes, the same way every time, and writes down what happened.**

---

## What the operator actually does

```
1. Plug the router in     →  2. Pick the gate  →  3. Scan the QR code  →  4. Press "Program Device"
   (per the wiring photo)     from a dropdown      on the router                and watch
```

Then they wait a few minutes while a checklist on screen ticks itself off:

```
  ✔ Scanning for Router      PASS
  ✔ Checking IP              PASS
  ✔ Firmware #1 install      PASS
  ✔ First reboot             PASS
  → Configuration push       1:47      ← currently running, with a timer
  ○ Switching static IP
  ○ Changing IP address
  ○ Testing
  ○ Making Label
```

Green means done. Red means that step failed and the run stopped. At the end, a label prints and a spreadsheet row gets filled in.

---

## The four things the app is made of

Think of it as four layers, each only talking to the one below it.

| Layer | What it is | Plain-language job |
| --- | --- | --- |
| **The screens** | `pages/` | What the operator sees and clicks. Four screens: welcome, add a device, program a device, wiring photo. |
| **The device folder** | `devices/TR/`, `devices/digiIX20/` | Everything specific to *one kind of router*. Its settings, its software, its spreadsheets, and the instructions for setting it up. |
| **The toolbox** | `resources/utilities/` | The shared, well-tested pieces every device needs: reading spreadsheets, talking to hardware, waiting properly, writing labels. |
| **The registry** | `core/` | The short list of which devices this workstation knows about. |

### The most important idea in the whole app

> **A "device" is a folder, not a piece of code.**

To teach the workstation a new kind of router, you don't write a new program — you drop in a **folder** containing that router's software and settings, and register it. That's it. No rebuilding, no programming. It works even on the installed, packaged version.

---

## What happens when you press the button

```
   Operator presses "Program Device"
              │
              ▼
   Look up the gate in the spreadsheet
   (What network address should this gate have?)
              │  If the spreadsheet is wrong or missing, stop HERE —
              │  before touching any hardware.
              ▼
   Run the router's own setup script
   (Load firmware → push settings → reboot → change address → test)
              │  This reports back after each step, which is
              │  what makes the checklist tick along live.
              ▼
   Write down what happened
   (Fill in the spreadsheet row, save a label, save an error log if it failed)
```

Two rules that are deliberate, and worth knowing:

- **A failed run gets a red timestamp in the spreadsheet, and no label.** A label for a router that didn't program is *worse* than no label — because somebody could stick it on a broken router and ship it.
- **A failed run still gets written down.** The red timestamp and the link to the error log are how a failure gets noticed later.

---

## The spreadsheet is the record

Each airport has a spreadsheet, one row per gate. The app reads the left-hand side to know what to do, and writes the right-hand side to record what it did.

| The app **reads** | The app **writes** |
| --- | --- |
| Gate number | MAC Address (the router's hardware ID) |
| Gate IP, Netmask, Gateway (the network address) | Router Programmed On — **black = worked, red = failed** |
| Serial number, part number | Label — a link to the label file |
| | Crash Report — a link to the error log, if it failed |
| | PRG # / Test # — how many attempts this gate has had |

**The columns are found by their headings, not by counting across.** That sounds like a small detail; it isn't. Counting across meant that if anyone inserted a column into a spreadsheet, the app quietly started reading and writing the *wrong* cells, with no error at all. It now looks for the words.

---

## The two routers, and why they look different

| | **Digi IX20** | **Teltonika RUTX08** |
| --- | --- | --- |
| Folder | `devices/digiIX20/` | `devices/TR/` |
| Live checklist on screen | Yes | No — console output only |
| Resumes after a failure | Yes, picks up where it left off | No, needs a factory reset |
| Built on the shared toolbox | Fully | The top half, yes. The part that talks to the router, not yet. |

The Digi is the newer, fully-modernised one. The Teltonika works, but the piece of it that actually talks to the router (`teltonika.py`) is still the original code and is the main remaining cleanup job.

---

## What the recent cleanup changed

The two routers had each grown their own private copy of the same housekeeping — reading spreadsheets, writing labels, saving error logs — and the copies had drifted apart. The cleanup moved all of it into one shared place.

| | Before | After |
| --- | --- | --- |
| Teltonika's control file | 943 lines | **361 lines** |
| Digi's control file | 353 lines | **104 lines** |
| Automated checks passing | 44 (plus 6 failing, 2 broken) | **66, all passing** |

It also fixed three real faults that had been hiding in the Teltonika code:

1. **Every run reported success — even the failures.** The program read the router's progress report twice, but reading it the first time used it up. All the fault-detection was in the second read, looking at nothing. So nothing was ever detected.
2. **A router that failed to set up was then tested anyway**, producing a second, more confusing failure on top of the first.
3. **Each test leaked a connection** to the test computer, until it eventually refused to accept any more.

And it deleted a folder called `device_types/` — four files that had been entirely commented out, doing nothing, while three screens still imported them.

---

## Where to look when something goes wrong

| Symptom | Look here |
| --- | --- |
| A gate's row has a **red timestamp** | Click the Crash Report link in that row |
| The app popped up an error window | The full text is also saved in `logs/` |
| The Gate dropdown is empty | That spreadsheet is missing its heading row, or the file is damaged |
| The "Program Device" button won't light up | Tick all the cabling checkboxes first — they're the gate |
| A `TR_...` setting seems half-ignored | Known: it reaches the Teltonika's outer layer but not `teltonika.py` yet |

---

## If you want to go deeper

| | |
| --- | --- |
| **Set up a new machine** | `SETUP.md` |
| **Use the app day to day** | `documentation/INSTRUCTIONS.md` |
| **How the pieces fit together** | `documentation/WORKFLOW.md` |
| **What each file and function does** | `documentation/CODE_EXPLAIN.md` |
| **The Teltonika specifically** | `devices/TR/documentation/` |
