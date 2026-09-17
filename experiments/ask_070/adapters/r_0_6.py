from ..contracts import ContractError


class R06Unavailable:
    package_id = "R_0_6"

    def identity_manifest(self):
        return {"package_id": self.package_id, "status": "NOT_YET_AVAILABLE", "implementation": None}

    def prepare(self, task):
        raise ContractError("REPRESENTATION_PACKAGE_NOT_AVAILABLE")

    def interpret(self, task, raw, *, error=None):
        raise ContractError("REPRESENTATION_PACKAGE_NOT_AVAILABLE")
