from app.backend.registration_discovery.datacite_provider import DataCiteRegistrationProvider
from app.backend.registration_discovery.direct_provider import DirectReferenceProvider
from app.backend.registration_discovery.domain import RegistrationDiscoveryRegistry
from app.backend.registration_discovery.osf_provider import OsfRegistrationProvider


def build_registration_discovery_registry() -> RegistrationDiscoveryRegistry:
    return (
        RegistrationDiscoveryRegistry()
        .register(DirectReferenceProvider())
        .register(OsfRegistrationProvider())
        .register(DataCiteRegistrationProvider())
    )
