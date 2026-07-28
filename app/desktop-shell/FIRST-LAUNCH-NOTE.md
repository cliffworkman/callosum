# Before you open Callosum for the first time

Download the installer for your platform from the
[latest release](https://github.com/cliffworkman/callosum/releases/latest) (scroll to "Assets").

Callosum isn't published through an app store yet, so your computer doesn't recognize it as coming
from a "known" publisher. That's not a sign anything is wrong — here's exactly what you'll see and
what to click.

## On Windows

You'll likely see a blue "Windows protected your PC" screen after double-clicking the installer.

1. Click **More info** (small text, easy to miss).
2. Click **Run anyway**.

That's it — the installer runs normally after that.

## On a Mac

The first time you open the app, macOS will show a small "Verifying 'Callosum'…" progress window
for a little while — that's normal (it's checking a genuinely large app), just let it finish.

After that, macOS will very likely refuse to open it, with **no visible option to override it in
that dialog** — this is the standard behavior for an app like this one that isn't from a registered
Apple developer. If that happens:

1. **Right-click** (or Control-click) the Callosum app icon instead of double-clicking.
2. Choose **Open** from the menu that appears.
3. A dialog will pop up again, but this time it has an **Open** button — click it.

You only need to do this once; after the first successful open, double-clicking works normally.

If neither of those dialogs shows an "Open"/"Run anyway" option, go to **System Settings → Privacy
& Security**, scroll down, and you should see a line about Callosum being blocked with an **Open
Anyway** button.

**If it instead says "Callosum is damaged and can't be opened" with only Move-to-Trash/Cancel and
no way to proceed at all** — don't trash it, that's not actually true; it's a sign the copy you have
is corrupted (a bad download, not a bad app). Grab a fresh copy from the
[latest release](https://github.com/cliffworkman/callosum/releases/latest) and try again; let me
know if it still happens.

## On Linux

You'll get a `.deb` file. Double-click it to open it with your software installer, or from a
terminal: `sudo dpkg -i Callosum_*_amd64.deb` (match the filename you downloaded). There's no
Gatekeeper/SmartScreen-style warning on Linux — it should just install and add Callosum to your
applications menu.

## Why this happens

Signing an app with Apple/Microsoft to skip these warnings costs money and takes time neither of us
have right now — this is genuinely just an unsigned build, not a red flag about the app itself.
Happy to walk through it together if anything looks different from what's described above.

## One more thing worth knowing

This is a very early build — a couple of things are still untested on real hardware you're actually
using (I've verified the mechanics through automated testing, but I haven't clicked through every
screen with my own eyes on your exact setup), so if something looks off, that's useful information,
not just an inconvenience. Let me know what you see.
