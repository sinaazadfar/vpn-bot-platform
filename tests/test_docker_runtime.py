from __future__ import annotations

from vpn_bot_platform.integrations.docker_runtime import (
    DockerRuntime,
    SellerRuntimeConfig,
    _docker_error_classes,
    seller_container_name,
)


class FakeImages:
    def get(self, image: str) -> object:
        return object()


class FakeContainers:
    def __init__(self) -> None:
        self.run_kwargs: dict[str, object] | None = None

    def get(self, name: str) -> object:
        _ImageNotFound, NotFound = _docker_error_classes()
        raise NotFound(name)

    def run(self, image: str, **kwargs: object) -> object:
        self.run_kwargs = {"image": image, **kwargs}
        return type("Container", (), {"id": "container-123"})()


class FakeDockerClient:
    def __init__(self) -> None:
        self.images = FakeImages()
        self.containers = FakeContainers()


def test_seller_container_name_is_stable() -> None:
    assert seller_container_name("abc-123") == "seller-abc-123"


def test_runtime_starts_seller_bot_entrypoint() -> None:
    runtime = object.__new__(DockerRuntime)
    runtime.config = SellerRuntimeConfig(
        image="vpn-bot-platform-seller:latest",
        network="vpn-bot-platform_default",
        label_prefix="vpn-bot-platform",
    )
    fake_client = FakeDockerClient()
    runtime.client = fake_client

    container_id = runtime.start_seller(
        seller_bot_id="abc-123",
        environment={"SELLER_BOT_ID": "abc-123"},
    )

    assert container_id == "container-123"
    assert fake_client.containers.run_kwargs is not None
    assert fake_client.containers.run_kwargs["command"] == [
        "python",
        "-m",
        "vpn_bot_platform.seller_bot.main",
    ]
    assert fake_client.containers.run_kwargs["volumes"] is None


def test_runtime_accepts_custom_command_and_data_volume() -> None:
    runtime = object.__new__(DockerRuntime)
    runtime.config = SellerRuntimeConfig(
        image="vpn-bot-platform-seller:latest",
        network="vpn-bot-platform_default",
        label_prefix="vpn-bot-platform",
        data_host_path="/opt/vpn-bot-platform/data/sellers",
    )
    fake_client = FakeDockerClient()
    runtime.client = fake_client

    container_id = runtime.start_seller(
        seller_bot_id="simple-123",
        environment={"BOT_TOKEN": "123:secret"},
        command=["python", "-m", "bot"],
    )

    assert container_id == "container-123"
    assert fake_client.containers.run_kwargs is not None
    assert fake_client.containers.run_kwargs["command"] == ["python", "-m", "bot"]
    assert fake_client.containers.run_kwargs["volumes"] == {
        "/opt/vpn-bot-platform/data/sellers": {
            "bind": "/app/data/sellers",
            "mode": "rw",
        }
    }
