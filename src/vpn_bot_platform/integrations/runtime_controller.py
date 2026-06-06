from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.integrations.docker_runtime import DockerRuntime, SellerRuntimeConfig


class SellerRuntimeController(Protocol):
    def start_seller(
        self,
        *,
        seller_bot_id: str,
        environment: dict[str, str],
        container_id: str | None = None,
    ) -> str:
        pass

    def stop_seller(self, *, container_id: str | None) -> None:
        pass

    def seller_logs(self, *, container_id: str | None, tail: int = 120) -> str:
        pass

    def seller_health(self, *, container_id: str | None) -> str:
        pass


@dataclass
class DockerSellerRuntimeController:
    runtime: DockerRuntime

    @classmethod
    def from_settings(cls, settings: Settings) -> DockerSellerRuntimeController:
        return cls(
            DockerRuntime(
                SellerRuntimeConfig(
                    image=settings.seller_runtime_image,
                    network=settings.seller_docker_network,
                    label_prefix=settings.seller_container_label_prefix,
                )
            )
        )

    def start_seller(
        self,
        *,
        seller_bot_id: str,
        environment: dict[str, str],
        container_id: str | None = None,
    ) -> str:
        return self.runtime.start_seller(
            seller_bot_id=seller_bot_id,
            environment=environment,
            container_id=container_id,
        )

    def stop_seller(self, *, container_id: str | None) -> None:
        self.runtime.stop_seller(container_id=container_id)

    def seller_logs(self, *, container_id: str | None, tail: int = 120) -> str:
        return self.runtime.seller_logs(container_id=container_id, tail=tail)

    def seller_health(self, *, container_id: str | None) -> str:
        return self.runtime.seller_health(container_id=container_id)
