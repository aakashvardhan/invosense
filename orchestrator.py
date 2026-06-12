"""CrewAI orchestrator: extraction -> compliance."""

from __future__ import annotations

import json
import logging
import os
from typing import Callable

from contracts import ComplianceResult, ExtractedInvoice
from mocks import compliance, extract

logger = logging.getLogger(__name__)

_USE_CREWAI = os.getenv("USE_CREWAI", "true").lower() == "true"


def run(image_path: str, invoice_id: str) -> tuple[ExtractedInvoice, ComplianceResult]:
    """Run the extract -> compliance chain."""
    if _USE_CREWAI:
        try:
            return _run_with_crewai(image_path, invoice_id)
        except Exception as exc:
            logger.warning("CrewAI orchestration failed, falling back to direct calls: %s", exc)

    return _run_direct(image_path, invoice_id)


def _run_direct(image_path: str, invoice_id: str) -> tuple[ExtractedInvoice, ComplianceResult]:
    extracted = extract.run(image_path, invoice_id)
    result = compliance.run(extracted)
    return extracted, result


def _run_with_crewai(image_path: str, invoice_id: str) -> tuple[ExtractedInvoice, ComplianceResult]:
    from crewai import Agent, Crew, Process, Task
    from crewai.tools import tool

    state: dict[str, ExtractedInvoice | ComplianceResult] = {}

    @tool("Extract structured invoice data from an attachment")
    def extract_invoice(_ctx: str = "") -> str:
        invoice = extract.run(image_path, invoice_id)
        state["extracted"] = invoice
        return json.dumps(invoice.to_dict())

    @tool("Run compliance checks on the extracted invoice")
    def check_compliance(_ctx: str = "") -> str:
        invoice = state["extracted"]
        if not isinstance(invoice, ExtractedInvoice):
            raise RuntimeError("Extraction must run before compliance")
        result = compliance.run(invoice)
        state["compliance"] = result
        return json.dumps(result.to_dict())

    llm = _build_llm()

    extractor = Agent(
        role="Invoice Extractor",
        goal="Extract structured invoice fields from attachments",
        backstory="Specialist in OCR and invoice field extraction.",
        tools=[extract_invoice],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    compliance_agent = Agent(
        role="Compliance Analyst",
        goal="Validate invoices against AP policy",
        backstory="Ensures vendor, amount, and duplicate checks pass.",
        tools=[check_compliance],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    extract_task = Task(
        description=(
            f"Extract invoice data from attachment at {image_path} "
            f"for invoice_id {invoice_id}. Call extract_invoice exactly once."
        ),
        expected_output="JSON object with extracted invoice fields",
        agent=extractor,
    )

    compliance_task = Task(
        description=(
            f"Run compliance checks for invoice_id {invoice_id}. "
            "Call check_compliance exactly once after extraction."
        ),
        expected_output="JSON object with compliance status and flags",
        agent=compliance_agent,
        context=[extract_task],
    )

    crew = Crew(
        agents=[extractor, compliance_agent],
        tasks=[extract_task, compliance_task],
        process=Process.sequential,
        verbose=False,
    )
    crew.kickoff()

    extracted = state.get("extracted")
    result = state.get("compliance")
    if not isinstance(extracted, ExtractedInvoice) or not isinstance(result, ComplianceResult):
        raise RuntimeError("CrewAI pipeline did not produce expected contract objects")

    return extracted, result


def _build_llm() -> str | Callable:
    """Prefer TrueFoundry / LiteLLM gateway when configured."""
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = os.getenv("TRUEFOUNDRY_LLM_GATEWAY_URL") or os.getenv("OPENAI_API_BASE")
    api_key = os.getenv("TRUEFOUNDRY_API_KEY") or os.getenv("OPENAI_API_KEY")

    if base_url and api_key:
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=0,
            )
        except ImportError:
            logger.debug("langchain_openai not installed; using model string for CrewAI")

    return model
