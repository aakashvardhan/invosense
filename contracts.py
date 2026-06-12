"""Shared contract shapes for the AP agent pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class ExtractedInvoice:
    invoice_id: str
    vendor_name: str
    vendor_id: str
    invoice_number: str
    invoice_date: str
    due_date: str
    currency: str
    subtotal: float
    tax: float
    total: float
    line_items: list[dict[str, Any]] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedInvoice:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ComplianceResult:
    invoice_id: str
    status: Literal["clean", "flagged"]
    flags: list[str] = field(default_factory=list)
    vendor_verified: bool = True
    amount_verified: bool = True
    duplicate_check_passed: bool = True
    notes: str = ""

    @property
    def has_flags(self) -> bool:
        return bool(self.flags) or self.status == "flagged"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplianceResult:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


Route = Literal["auto_pay", "human_review"]


@dataclass
class Decision:
    invoice_id: str
    route: Route
    reason: str
    extracted: ExtractedInvoice
    compliance: ComplianceResult
    policy_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "route": self.route,
            "reason": self.reason,
            "extracted": self.extracted.to_dict(),
            "compliance": self.compliance.to_dict(),
            "policy_snapshot": self.policy_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        return cls(
            invoice_id=data["invoice_id"],
            route=data["route"],
            reason=data["reason"],
            extracted=ExtractedInvoice.from_dict(data["extracted"]),
            compliance=ComplianceResult.from_dict(data["compliance"]),
            policy_snapshot=data.get("policy_snapshot", {}),
        )


@dataclass
class PaymentResult:
    invoice_id: str
    success: bool
    payment_id: str
    amount: float
    currency: str
    status: Literal["completed", "skipped", "failed"]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaymentResult:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PublishResult:
    invoice_id: str
    success: bool
    destination: str
    record_id: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PublishResult:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
