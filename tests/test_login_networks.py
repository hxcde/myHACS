"""Login monitor: IPv6 privacy addresses and known providers are no "new IP" alarm."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant

from custom_components.bastion.login_monitor import network_of

from .test_integration import _mock_web, _setup

# Documentation addresses (RFC 3849), treated as public in the test.
MOBILE_A = "2001:db8:aaaa:1:1111:2222:3333:4444"
MOBILE_B = "2001:db8:aaaa:1:5555:6666:7777:8888"  # same /64, new privacy address
MOBILE_C = "2001:db8:aaaa:2:9999:aaaa:bbbb:cccc"  # new /64, same provider
HOME = "2001:db8:bbbb:1:dddd:eeee:ffff:1"  # other provider
OTHER = "2001:db8:aaaa:3::7"


def test_network_of() -> None:
    assert network_of(MOBILE_A) == network_of(MOBILE_B) == "2001:db8:aaaa:1::/64"
    assert network_of(MOBILE_A) != network_of(MOBILE_C)
    assert network_of("203.0.113.7") == "203.0.113.7"
    assert network_of("203.0.113.8") != network_of("203.0.113.7"), "IPv4 stays exact"
    assert network_of("::ffff:203.0.113.7") == "203.0.113.7"
    assert network_of("nonsense") == "nonsense"


async def test_new_address_of_a_known_provider_is_quiet(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    for ip, asn, isp, city in (
        (MOBILE_A, 64500, "Mobile Provider", "Exampletown"),
        (MOBILE_C, 64500, "Mobile Provider", "Exampletown"),
        (OTHER, 64500, "Mobile Provider", "Exampletown"),
        (HOME, 64501, "Home Provider", "Exampleville"),
    ):
        aioclient_mock.get(
            f"https://ipwho.is/{ip}?fields=country,country_code,city,connection",
            json={"city": city, "country": "Germany", "country_code": "DE", "connection": {"asn": asn, "isp": isp}},
        )
    entry = await _setup(hass, tmp_path, {"geoip_lookup": True})
    logins = entry.runtime_data.logins
    seen = []

    async def capture(kind, data, *, notify=True, **_):
        seen.append((kind, data, notify))

    logins._async_event = capture  # noqa: SLF001
    info = {"user": "anna", "user_id": "u1", "name": "https://home-assistant.io/iOS"}
    check = logins._async_check_ip  # noqa: SLF001
    public = patch("custom_components.bastion.login_monitor.is_public_ip", return_value=True)
    public.start()
    await check(info, "t1", MOBILE_A, True, True)
    assert seen[-1][0] == "new_ip" and seen[-1][2] is True, "first address of a new provider: push"
    assert seen[-1][1]["isp"] == "Mobile Provider" and seen[-1][1]["known_provider"] is False
    count = len(seen)
    await check(info, "t1", MOBILE_B, True, True)
    assert len(seen) == count, "new privacy address in the same /64: nothing"
    await check(info, "t1", MOBILE_C, True, True)
    assert seen[-1][1]["known_provider"] is True and seen[-1][2] is False, "same provider: logged, no push"
    await check(info, "t1", HOME, True, True)
    assert seen[-1][1]["known_provider"] is False and seen[-1][2] is True, "other provider: push"
    # Persisted with the rest of the login state.
    assert logins._data()["known_providers"]["u1"] == ["64500|DE", "64501|DE"]  # noqa: SLF001
    public.stop()
