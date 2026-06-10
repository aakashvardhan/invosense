import { pay } from "../actions/pay.js";
import { publish } from "../actions/publish.js";
import type { Decision, PaymentResult } from "../actions/pay.js";
import type { PublishResult } from "../actions/publish.js";

// ── State ──────────────────────────────────────────────────────────────────

export type InvoiceStatus =
  | "processing"
  | "PAY_QUEUED"
  | "PAID"
  | "FLAG"
  | "HUMAN_REVIEW"
  | "REJECTED"
  | "ERROR";

export interface InvoiceRecord {
  decision:  Decision;
  status:    InvoiceStatus;
  payment?:  PaymentResult;
  publish?:  PublishResult;
  error?:    string;
}

// In-memory store (keyed by invoice_id).
const store = new Map<string, InvoiceRecord>();

// ── Initialisation ─────────────────────────────────────────────────────────

/**
 * Load Decision objects into the store and kick off automatic processing
 * for "PAY" decisions. FLAG and HUMAN_REVIEW decisions are stored as-is.
 */
export function loadDecisions(decisions: Decision[]): void {
  for (const d of decisions) {
    const initial: InvoiceStatus =
      d.decision === "PAY"
        ? "PAY_QUEUED"
        : d.decision === "FLAG"
        ? "FLAG"
        : "HUMAN_REVIEW";

    store.set(d.invoice_id, { decision: d, status: initial });

    // Auto-process PAY decisions asynchronously so the server starts quickly
    // and the UI shows the "processing" → "PAID" transition in real time.
    if (d.decision === "PAY") {
      setImmediate(() => processPay(d.invoice_id));
    }
  }

  console.log(`[INVOICES] Loaded ${decisions.length} decisions into store`);
}

// ── Helpers ────────────────────────────────────────────────────────────────

async function processPay(invoiceId: string): Promise<void> {
  const record = store.get(invoiceId);
  if (!record) return;

  store.set(invoiceId, { ...record, status: "processing" });

  try {
    const payment = await pay(record.decision);
    const pub     = await publish(record.decision, payment);

    store.set(invoiceId, {
      ...record,
      status:  "PAID",
      payment,
      publish: pub,
    });
    console.log(`[INVOICES] Auto-processed PAY → PAID: ${invoiceId}`);
  } catch (err) {
    const error = err instanceof Error ? err.message : String(err);
    store.set(invoiceId, { ...record, status: "ERROR", error });
    console.error(`[INVOICES] PAY failed for ${invoiceId}: ${error}`);
  }
}

// ── Route handlers ─────────────────────────────────────────────────────────

/** GET /invoices — returns all records in the store. */
export function getAllInvoices(): InvoiceRecord[] {
  return Array.from(store.values());
}

/** POST /invoices/:id/approve — pay + publish a HUMAN_REVIEW invoice. */
export async function approveInvoice(
  invoiceId: string
): Promise<InvoiceRecord> {
  const record = store.get(invoiceId);
  if (!record) throw new Error(`Invoice "${invoiceId}" not found`);
  if (record.status !== "HUMAN_REVIEW") {
    throw new Error(
      `Invoice "${invoiceId}" is in status "${record.status}", expected "HUMAN_REVIEW"`
    );
  }

  store.set(invoiceId, { ...record, status: "processing" });

  try {
    const payment = await pay(record.decision);
    const pub     = await publish(record.decision, payment);

    const updated: InvoiceRecord = {
      ...record,
      status:  "PAID",
      payment,
      publish: pub,
    };
    store.set(invoiceId, updated);
    console.log(`[INVOICES] HUMAN_REVIEW approved → PAID: ${invoiceId}`);
    return updated;
  } catch (err) {
    const error = err instanceof Error ? err.message : String(err);
    store.set(invoiceId, { ...record, status: "ERROR", error });
    throw new Error(`Approval failed for ${invoiceId}: ${error}`);
  }
}

/** POST /invoices/:id/reject — mark a HUMAN_REVIEW invoice as REJECTED (no payment). */
export function rejectInvoice(invoiceId: string): InvoiceRecord {
  const record = store.get(invoiceId);
  if (!record) throw new Error(`Invoice "${invoiceId}" not found`);
  if (record.status !== "HUMAN_REVIEW") {
    throw new Error(
      `Invoice "${invoiceId}" is in status "${record.status}", expected "HUMAN_REVIEW"`
    );
  }

  const updated: InvoiceRecord = { ...record, status: "REJECTED" };
  store.set(invoiceId, updated);
  console.log(`[INVOICES] HUMAN_REVIEW rejected: ${invoiceId}`);
  return updated;
}
