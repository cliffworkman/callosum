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
from com.sun.star.task import XJob, XJobExecutor


def _import_adapter(ctx):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import callosum_cite as cc

    cc._DISPATCH_CTX = ctx
    return cc


def _job_model(args):
    """Extract the XModel supplied for a Jobs.xcu DOCUMENTEVENT execution."""
    for outer in args:
        if outer.Name != "Environment":
            continue
        for item in outer.Value:
            if item.Name == "Model":
                return item.Value
    return None


class Dispatcher(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx

    def trigger(self, arg):
        cc = _import_adapter(self.ctx)
        try:
            desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            cc.dispatch(str(arg), desktop.getCurrentComponent(), cc._base())
        except cc.RefreshCancelled:
            pass
        except Exception as exc:  # surface, never crash Writer
            try:
                cc._msgbox(f"{arg}: {exc}")
            except Exception:
                pass


class DocumentLifecycleJob(unohelper.Base, XJob):
    """Restore persisted state and begin structured-change observation as soon as a Writer file opens."""

    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self, args):
        try:
            model = _job_model(args)
            if model is not None:
                _import_adapter(self.ctx).observe_document(model)
        except Exception:
            pass
        return None


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Dispatcher, "com.callosum.cite.Dispatcher", ("com.callosum.cite.Dispatcher",))
g_ImplementationHelper.addImplementation(
    DocumentLifecycleJob,
    "com.callosum.cite.DocumentLifecycle",
    ("com.callosum.cite.DocumentLifecycle",),
)
