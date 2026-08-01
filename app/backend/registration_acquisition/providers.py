from app.backend.registration_acquisition.aspredicted import AsPredictedRegistrationAcquirer
from app.backend.registration_acquisition.domain import RegistrationAcquisitionRegistry
from app.backend.registration_acquisition.osf import OsfRegistrationAcquirer


def build_registration_acquisition_registry() -> RegistrationAcquisitionRegistry:
    return (
        RegistrationAcquisitionRegistry()
        .register(OsfRegistrationAcquirer())
        .register(AsPredictedRegistrationAcquirer())
    )
