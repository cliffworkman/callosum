"""callosum — LibreOffice .oxt dispatcher component (inc 162).

A tiny UNO ``XJobExecutor`` so the **Callosum** menu/toolbar items (declared in ``Addons.xcu``) can invoke the
Python actions in ``callosum_cite.py``. Each menu/toolbar item's URL is ``service:com.callosum.cite.Dispatcher?<action>``;
the LibreOffice ``service:`` dispatch protocol instantiates this component and calls ``trigger("<action>")``.

Why a component (not a ``vnd.sun.star.script:`` URL): the script-path URI for an extension-bundled macro depends on
the generated package folder name and is fragile. A registered service is path-independent and is the standard way
to wire menu/toolbar actions to Python in an `.oxt`.

The actions live in ``callosum_cite`` (the same file you can also install by hand as a macro). Its dialog helpers
rely on the macro-only ``XSCRIPTCONTEXT`` global, which does NOT exist in a component — so we bridge our component
context into it (``cc._DISPATCH_CTX``) and resolve the current Writer document via the Desktop.

``callosum_cite`` is imported **lazily inside trigger()**, after putting this component's own directory on
``sys.path``: at *registration* time (``unopkg add``) the extension directory is not yet importable, so a top-level
``import callosum_cite`` would fail registration. By dispatch time the file sits beside this one in the installed
package, so the path insert makes the sibling import resolve.
"""

import os
import sys

import unohelper
from com.sun.star.task import XJobExecutor


class Dispatcher(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx

    def trigger(self, arg):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # make the sibling callosum_cite importable
        import callosum_cite as cc

        cc._DISPATCH_CTX = self.ctx  # let cc's dialog helpers find a component context (no XSCRIPTCONTEXT here)
        try:
            desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            cc.dispatch(str(arg), desktop.getCurrentComponent(), cc._base())
        except Exception as exc:  # surface, never crash Writer
            try:
                cc._msgbox(f"{arg}: {exc}")
            except Exception:
                pass


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Dispatcher, "com.callosum.cite.Dispatcher", ("com.callosum.cite.Dispatcher",))
