from typing import Protocol

from ..contracts import FrozenTask


class RepresentationPackage(Protocol):
    package_id: str

    def prepare(self, task: FrozenTask) -> dict: ...

    def interpret(self, task: FrozenTask, raw: str, *, error: str | None = None) -> dict: ...

    def identity_manifest(self) -> dict: ...


def get_package(package_id):
    if package_id == "R_CONTROL":
        from .r_control import RControl

        return RControl()
    if package_id == "R_0_6":
        from .r_0_6 import R06Unavailable

        return R06Unavailable()
    raise ValueError("UNKNOWN_REPRESENTATION_PACKAGE")
