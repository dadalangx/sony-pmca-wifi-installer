"""Windows Mobile Hotspot, through the supported WinRT API."""
import asyncio

from .i18n import UserError


class HotspotError(UserError):
    pass


class HotspotSession:
    def __init__(self):
        self.manager = None
        self.previous = None
        self.changed = False
        self.started = False

    async def start(self, ssid, password):
        from winrt.windows.networking.connectivity import NetworkInformation
        from winrt.windows.networking.networkoperators import (
            NetworkOperatorTetheringManager as Manager,
            NetworkOperatorTetheringAccessPointConfiguration as Configuration,
            TetheringCapability, TetheringOperationalState,
            TetheringOperationStatus, TetheringWiFiBand,
        )
        profile = NetworkInformation.get_internet_connection_profile()
        if profile is None:
            raise HotspotError("internet_required")
        capability = Manager.get_tethering_capability_from_connection_profile(profile)
        if capability != TetheringCapability.ENABLED:
            raise HotspotError("hotspot_capability", code=capability.name)
        self.manager = Manager.create_from_connection_profile(profile)
        if self.manager.tethering_operational_state != TetheringOperationalState.OFF:
            raise HotspotError("mobile_active")
        self.previous = self.manager.get_current_access_point_configuration()
        config = Configuration()
        config.ssid = ssid
        config.passphrase = password
        band = TetheringWiFiBand.TWO_POINT_FOUR_GIGAHERTZ
        # Older 2.4 GHz-only drivers cannot select a band through this API.
        # Let Windows select it, then verify camera connectivity in the wizard.
        if not await config.is_band_supported_async(band):
            band = TetheringWiFiBand.AUTO
        config.band = band
        # Mark before the asynchronous mutation so failure still restores state.
        self.changed = True
        try:
            await self.manager.configure_access_point_async(config)
            result = await self.manager.start_tethering_async()
            if result.status != TetheringOperationStatus.SUCCESS:
                raise HotspotError("mobile_start", code=result.status.name, detail=result.additional_error_message)
            self.started = True
        except BaseException:
            await self.close()
            raise
        return {"ssid": ssid, "password": password, "band": band.name}

    def clients(self):
        if not self.manager or not self.started:
            return []
        return [{"mac": c.mac_address} for c in self.manager.get_tethering_clients()]

    async def close(self):
        from winrt.windows.networking.networkoperators import TetheringOperationalState, TetheringOperationStatus
        if not self.manager or not self.changed:
            return
        if self.manager.tethering_operational_state != TetheringOperationalState.OFF:
            result = await self.manager.stop_tethering_async()
            if result.status != TetheringOperationStatus.SUCCESS:
                raise HotspotError("mobile_stop", code=result.status.name)
        self.started = False
        await self.manager.configure_access_point_async(self.previous)
        self.changed = False


async def smoke_test(seconds=1200):
    """Bounded manual hardware test; always restore the previous configuration."""
    import json
    import time
    from pathlib import Path
    from winrt.windows.networking.connectivity import NetworkInformation
    from winrt.windows.networking.networkoperators import NetworkOperatorTetheringManager, TetheringOperationalState
    manager = NetworkOperatorTetheringManager.create_from_connection_profile(NetworkInformation.get_internet_connection_profile())
    if manager.tethering_operational_state == TetheringOperationalState.ON:
        if manager.get_current_access_point_configuration().ssid not in ("Sony-App-Setup", "SONYSETUP"):
            raise HotspotError("mobile_active")
        await manager.stop_tethering_async()
    stop = Path(__file__).resolve().parents[1] / ".local" / "stop-hotspot-lab"
    stop.unlink(missing_ok=True)
    session = HotspotSession()
    try:
        print(json.dumps(await session.start("SONYSETUP", "24682468")), flush=True)
        deadline = time.monotonic() + seconds
        previous = None
        while time.monotonic() < deadline and not stop.exists():
            clients = session.clients()
            if clients != previous:
                print(json.dumps({"clients": clients}), flush=True)
                previous = clients
            await asyncio.sleep(2)
    finally:
        await session.close()
        print("Hotspot configuration restored.", flush=True)


if __name__ == "__main__":
    asyncio.run(smoke_test())
