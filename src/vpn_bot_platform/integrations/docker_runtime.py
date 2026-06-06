from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SellerRuntimeConfig:
    image: str
    network: str | None
    label_prefix: str


class DockerRuntime:
    def __init__(self, config: SellerRuntimeConfig) -> None:
        self.config = config
        self.client = self._create_client()

    def _create_client(self):
        import docker

        docker_host = os.getenv("DOCKER_HOST", "")
        if docker_host.startswith("http+docker"):
            return docker.DockerClient(base_url="unix:///var/run/docker.sock")
        if os.path.exists("/var/run/docker.sock"):
            return docker.DockerClient(base_url="unix:///var/run/docker.sock")
        return docker.from_env()

    def _labels(self, seller_bot_id: str) -> dict[str, str]:
        return {
            f"{self.config.label_prefix}.seller_bot_id": seller_bot_id,
            f"{self.config.label_prefix}.managed": "true",
        }

    def start_seller(
        self,
        *,
        seller_bot_id: str,
        environment: dict[str, str],
        container_id: str | None = None,
    ) -> str:
        from docker.errors import ImageNotFound, NotFound

        try:
            self.client.images.get(self.config.image)
        except ImageNotFound:
            raise RuntimeError(f"Seller runtime image not found: {self.config.image}") from None

        name = seller_container_name(seller_bot_id)
        if container_id:
            try:
                existing = self.client.containers.get(container_id)
                existing.remove(force=True)
            except NotFound:
                pass

        try:
            stale = self.client.containers.get(name)
            stale.remove(force=True)
        except NotFound:
            pass

        container = self.client.containers.run(
            self.config.image,
            detach=True,
            name=name,
            environment=environment,
            labels=self._labels(seller_bot_id),
            network=self.config.network,
            restart_policy={"Name": "unless-stopped"},
        )
        return container.id

    def stop_seller(self, *, container_id: str | None) -> None:
        if not container_id:
            return
        from docker.errors import NotFound

        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=10)
        except NotFound:
            return

    def seller_logs(self, *, container_id: str | None, tail: int = 120) -> str:
        if not container_id:
            return ""
        from docker.errors import NotFound

        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode("utf-8", errors="ignore")
        except NotFound:
            return ""

    def seller_health(self, *, container_id: str | None) -> str:
        if not container_id:
            return "missing"
        from docker.errors import NotFound

        try:
            container = self.client.containers.get(container_id)
            container.reload()
            state = container.attrs.get("State", {})
            if "Health" in state:
                return str(state["Health"].get("Status", "unknown"))
            return str(state.get("Status", "unknown"))
        except NotFound:
            return "missing"


def seller_container_name(seller_bot_id: str) -> str:
    return f"seller-{seller_bot_id}"

