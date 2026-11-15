"""Buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BastionEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """Set up buttons."""
    bastion = entry.runtime_data
    entities = [RunAuditButton(bastion), ReportButton(bastion)]
    if bastion.git.enabled:
        entities.append(GitCommitButton(bastion))
    if bastion.options.get("probe_url"):
        entities.append(ProbeButton(bastion))
    async_add_entities(entities)


class RunAuditButton(BastionEntity, ButtonEntity):
    """Run the audit."""

    _attr_icon = "mdi:shield-search"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "run_audit")

    async def async_press(self) -> None:
        await self.bastion.async_run_audit()


class GitCommitButton(BastionEntity, ButtonEntity):
    """Commit the configuration now."""

    _attr_icon = "mdi:source-commit-local"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "git_commit")

    async def async_press(self) -> None:
        await self.bastion.git.async_commit("manual")


class ProbeButton(BastionEntity, ButtonEntity):
    """Run the external port check."""

    _attr_icon = "mdi:web-check"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "external_scan")

    async def async_press(self) -> None:
        await self.bastion.async_run_probe()


class ReportButton(BastionEntity, ButtonEntity):
    """Send the weekly report now."""

    _attr_icon = "mdi:file-chart"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "send_report")

    async def async_press(self) -> None:
        await self.bastion.async_send_report()
