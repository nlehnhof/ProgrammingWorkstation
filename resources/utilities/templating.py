"""Working copies of the pristine template files a device ships with.

Every device keeps two versions of the files it pushes to hardware: an
`og_*` original that is never edited, and a working copy that each run rewrites
for the gate being programmed. `devices/TR/` has two such pairs --
`og_configs/`/`configs/` and `og_testfile/`/`testfile/`.

The pattern is always the same: refresh the working copy from the original,
substitute this gate's address for the placeholder, then *verify the
substitution actually happened* before shipping the file anywhere. That last
step is the point. The old code checked with `if new_ip in content`, which is
satisfied by a file that already contained the address from a previous run --
so a substitution that silently failed still looked fine, and the previous
gate's configuration went onto this gate's router.
"""

import os
import re
import shutil


class TemplateError(RuntimeError):
    """A template could not be staged or patched."""


def refresh_working_copy(source_dir, dest_dir):
    """Re-copy every file from `source_dir` into `dest_dir`.

    Returns the list of filenames copied. Subdirectories are ignored -- both
    template folders here are flat, and recursing would pick up a stray
    `__pycache__`.
    """
    if not os.path.isdir(source_dir):
        raise TemplateError(f"Template folder not found: {source_dir}")

    os.makedirs(dest_dir, exist_ok=True)

    copied = []
    for name in sorted(os.listdir(source_dir)):
        source = os.path.join(source_dir, name)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(dest_dir, name))
            copied.append(name)

    if not copied:
        raise TemplateError(f"Template folder is empty: {source_dir}")
    return copied


def patch_file(path, old, new, occurrences=None):
    """Replace `old` with `new` in `path`, verifying the edit landed.

    Matches `old` as a whole token, so replacing "10.28.18.2" cannot corrupt
    "10.28.18.20" sitting elsewhere in the same file.

    Verification counts the replacements made rather than checking that `new`
    appears afterwards -- see the module docstring for why the latter is not
    good enough.

    :param occurrences: if given, the exact number of replacements expected.
    :raises TemplateError: if nothing was replaced, or the count disagrees.
    """
    old, new = str(old), str(new)

    if old == new:
        # Nothing to do, and nothing to verify. Happens when a gate legitimately
        # sits on the template address.
        return 0

    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except OSError as exc:
        raise TemplateError(f"Could not read {path}: {exc}") from exc

    pattern = re.compile(rf"(?<![\w.]){re.escape(old)}(?![\w.])")
    updated, count = pattern.subn(new, content)

    if count == 0:
        raise TemplateError(
            f"{os.path.basename(path)} does not contain {old!r}, so it could not "
            f"be pointed at {new!r}. The template may already have been edited."
        )
    if occurrences is not None and count != occurrences:
        raise TemplateError(
            f"{os.path.basename(path)} contained {count} copies of {old!r}, "
            f"expected {occurrences}."
        )

    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(updated)
    except OSError as exc:
        raise TemplateError(f"Could not write {path}: {exc}") from exc

    print(f"{os.path.basename(path)}: {old} -> {new} ({count} replaced)", flush=True)
    return count


def stage_template(source_dir, dest_dir, filename, old, new):
    """Refresh one template folder and point `filename` at `new`.

    Returns the path of the patched working copy.
    """
    refresh_working_copy(source_dir, dest_dir)
    path = os.path.join(dest_dir, filename)
    if not os.path.isfile(path):
        raise TemplateError(f"{filename} is not in {source_dir}")
    patch_file(path, old, new)
    return path
