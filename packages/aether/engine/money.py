"""Money as integer cents — never float for capital/risk."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Money:
    """USD amount stored as integer cents (i64-safe range in practice)."""

    cents: int

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int):
            raise TypeError("Money.cents must be int")

    @staticmethod
    def from_usd(x: float | int) -> Money:
        # banker's? no — round half away from zero for simplicity on research path
        return Money(int(round(float(x) * 100.0)))

    def usd(self) -> float:
        return self.cents / 100.0

    def __add__(self, other: Money) -> Money:
        return Money(self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        return Money(self.cents - other.cents)

    def __mul__(self, k: float | int) -> Money:
        return Money(int(round(self.cents * float(k))))

    def __neg__(self) -> Money:
        return Money(-self.cents)

    def __lt__(self, other: Money) -> bool:
        return self.cents < other.cents

    def __le__(self, other: Money) -> bool:
        return self.cents <= other.cents

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents == other.cents

    def __repr__(self) -> str:
        return f"Money(${self.usd():,.2f})"
