from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PaymentIntent:
    provider: str
    instructions: str
    external_reference: str | None = None


class PaymentGatewayAdapter(Protocol):
    provider: str

    def create_payment_intent(
        self,
        *,
        amount: float,
        description: str,
        buyer_telegram_id: int,
    ) -> PaymentIntent:
        pass


@dataclass(frozen=True)
class CardToCardGatewayAdapter:
    instructions: str
    provider: str = "card_to_card"

    def create_payment_intent(
        self,
        *,
        amount: float,
        description: str,
        buyer_telegram_id: int,
    ) -> PaymentIntent:
        return PaymentIntent(
            provider=self.provider,
            instructions=self.instructions,
            external_reference=f"manual:{buyer_telegram_id}:{int(amount)}",
        )


class PaymentGatewayRegistry:
    def __init__(self, adapters: list[PaymentGatewayAdapter]) -> None:
        self._adapters = {adapter.provider: adapter for adapter in adapters}

    def get(self, provider: str) -> PaymentGatewayAdapter:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise ValueError(f"payment_gateway_not_configured:{provider}")
        return adapter


def default_payment_registry(*, card_to_card_instructions: str) -> PaymentGatewayRegistry:
    return PaymentGatewayRegistry(
        [
            CardToCardGatewayAdapter(instructions=card_to_card_instructions),
        ]
    )
