from __future__ import annotations

import os
from dataclasses import dataclass


class _FallbackImageNotFound(Exception):
    pass


class _FallbackNotFound(Exception):
    pass


@dataclass(frozen=True)
class SellerRuntimeConfig:
    image: str
    network: str | None
    label_prefix: str
    data_host_path: str | None = None


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
        command: list[str] | None = None,
    ) -> str:
        ImageNotFound, NotFound = _docker_error_classes()

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

        volumes = None
        if self.config.data_host_path:
            volumes = {
                self.config.data_host_path: {
                    "bind": "/app/data/sellers",
                    "mode": "rw",
                }
            }

        container = self.client.containers.run(
            self.config.image,
            command=command or ["python", "-m", "vpn_bot_platform.seller_bot.main"],
            detach=True,
            name=name,
            environment=environment,
            labels=self._labels(seller_bot_id),
            network=self.config.network,
            volumes=volumes,
            restart_policy={"Name": "unless-stopped"},
        )
        return container.id

    def stop_seller(self, *, container_id: str | None) -> None:
        if not container_id:
            return
        _ImageNotFound, NotFound = _docker_error_classes()

        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=10)
        except NotFound:
            return

    def seller_logs(self, *, container_id: str | None, tail: int = 120) -> str:
        if not container_id:
            return ""
        _ImageNotFound, NotFound = _docker_error_classes()

        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode("utf-8", errors="ignore")
        except NotFound:
            return ""

    def seller_health(self, *, container_id: str | None) -> str:
        if not container_id:
            return "missing"
        _ImageNotFound, NotFound = _docker_error_classes()

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


def _docker_error_classes():
    try:
        from docker.errors import ImageNotFound, NotFound
    except ModuleNotFoundError:
        ImageNotFound = _FallbackImageNotFound
        NotFound = _FallbackNotFound

    return ImageNotFound, NotFound
