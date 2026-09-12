# Working in labscript-utils

This repository is the library the rest of the suite imports, not an
application. There is no `__main__.py` here, so the "never import `__main__`"
rule that the application repositories carry does not apply. The corresponding
hazard is the opposite one: a change here reaches blacs, runmanager, lyse,
runviewer, labscript and labscript-devices at once, and several of the things
below are load-bearing for code that does not live in this repository.

Importing `labscript_utils.splash` creates no `QApplication` — only
constructing `Splash` does. That is what lets the sibling repositories stub
this module in `sys.modules` and borrow real application methods without
putting a banner on screen. Keep it that way.

## Tests

`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` before Qt is imported, so
a test run puts nothing on the screen of whoever runs it. It has to be a
conftest rather than a fixture because it must take effect before qtutils
imports Qt, and pytest imports conftest before the test modules. `setdefault`
leaves an explicit setting alone, so you can export the variable yourself to
watch a test drive a widget.

`tests/test_shotqueue.py` shows a real widget, and is right to. Qt does not lay
out or paint a widget that was never shown, so its pixel measurements read
nothing without it. **Do not "fix" a visible window by removing the `show()`** —
the assertions would then pass vacuously. Offscreen rendering is what lets the
test go on showing a real window without one appearing, and it still genuinely
measures: drop the rule's alpha from 140 to 6 and the test fails at 0.016
luminance.

It guards the one visual mark a running shot has, and it is the only test in
the suite that grabs a rendered widget and measures its pixels. That is what
exposes it to the `devicePixelRatio` trap it documents in place: `grab()`
returns device pixels while `visualRect()` returns logical ones, so on a retina
display reading the image at logical coordinates samples the wrong row and
reports a contrast of exactly zero. Read that comment before touching anything
that measures rendered output.

`runmanager/tests/test_blacs_status.py` also compares images, but it renders two
pixmaps from a `QIcon` at a fixed size and asserts they differ. It never shows a
widget, never grabs one, and has no exposure to the trap — so it is not a
precedent for how to write one that does.

### Running them

From inside this repository, never from the workspace root. A workspace-root
cwd turns the sibling checkouts into namespace packages that shadow the
installed ones, so `import zprocess` finds the repository directory instead:

    ~/miniforge3/envs/labscript/bin/python -m pytest tests -q

## Invariants that are easy to tidy into a bug

**`lookup_format` brace escaping.** `format_lookup_string()` escapes braces
only when preservation is enabled, because that is exactly the case where its
output is a template for a further pass rather than final text.
`unescape_braces()` is the exact inverse, and the two live next to each other so
they cannot drift. runmanager calls the unescaper in
`get_default_output_folder()` because that value is *displayed*; the other
`new_sequence_details()` call sites must not, because their value is fed to the
per-shot pass and needs the escaping to survive it. Unescaping centrally looks
like a tidy-up and silently breaks per-shot output paths.

**Config values are natively typed.** Since the TOML migration
`LabConfig.get()` returns real ints, floats, bools and lists rather than
strings. Anything treating a labconfig option as a string — `.split(',')` on a
path list is the one that bit — needs `labscript_profile.toml_config.as_config_list()`
or an equivalent. Both places it bit ran before anyone could catch it:
`_get_device_dirs()` at module scope, so `import labscript_utils.device_registry`
raised and took four applications with it, and `add_userlib_and_pythonlib()`
from `labscript-suite.pth`, so it fired at every interpreter start and left
`userlib` off `sys.path` for the whole session.

**App config paths append, they do not replace.** `appconfig_path_with_suffix()`
exists because `Path.with_suffix()` truncates at the last dot, which silently
addresses a different file for any name that legitimately contains one — an
analysis script called `rb.87.imaging`, for instance. Use it rather than
`with_suffix()` for anything under `save_appconfig`/`load_appconfig`.
