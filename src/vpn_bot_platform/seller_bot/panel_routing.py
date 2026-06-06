from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot_platform.common.models import MarzbanPanel, ResellerPanelAssignment
from vpn_bot_platform.common.repositories import list_active_panel_assignments


@dataclass(frozen=True)
class RoutedPanel:
    assignment: ResellerPanelAssignment
    panel: MarzbanPanel


class PanelRouter:
    async def choose_panel(
        self,
        session: AsyncSession,
        *,
        reseller_id: str,
    ) -> RoutedPanel | None:
        assignments = await list_active_panel_assignments(session, reseller_id=reseller_id)
        if not assignments:
            return None
        assignment, panel = assignments[0]
        return RoutedPanel(assignment=assignment, panel=panel)
