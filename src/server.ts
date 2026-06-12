import "dotenv/config";
import express from "express";
import cors from "cors";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import {
  loadDecisions,
  getAllInvoices,
  approveInvoice,
  rejectInvoice,
} from "./api/invoices.js";
import { loadDecisionsFromOut, resolveOutDir } from "./api/ingest.js";
import type { Decision } from "./actions/pay.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const OUT_DIR = resolveOutDir(ROOT);

// ── Bootstrap data ─────────────────────────────────────────────────────────
// Prefer real OCR-pipeline output (out/). Fall back to bundled mocks so the
// app still runs when the OCR directory is absent.

function loadMockDecisions(): Decision[] {
  try {
    const raw = readFileSync(resolve(ROOT, "mocks/decisions.json"), "utf-8");
    return JSON.parse(raw) as Decision[];
  } catch (err) {
    console.error("[SERVER] Could not load mocks/decisions.json:", err);
    return [];
  }
}

function bootstrapDecisions(): { source: string; decisions: Decision[] } {
  const fromOut = loadDecisionsFromOut(OUT_DIR);
  if (fromOut.length > 0) {
    return { source: `OCR output (${OUT_DIR})`, decisions: fromOut };
  }
  return { source: "mocks/decisions.json", decisions: loadMockDecisions() };
}

const { source, decisions } = bootstrapDecisions();
loadDecisions(decisions);

// ── Express app ────────────────────────────────────────────────────────────

const app = express();

app.use(cors());
app.use(express.json());

// Serve the React frontend from /public
app.use(express.static(resolve(ROOT, "public")));

// Serve the annotated OCR invoice images (with bounding boxes) from out/
app.use("/invoice-images", express.static(OUT_DIR));

// ── API routes ─────────────────────────────────────────────────────────────

/** GET /invoices — all decisions + current status */
app.get("/invoices", (_req, res) => {
  res.json(getAllInvoices());
});

/** POST /invoices/:id/approve — trigger pay + publish for a HUMAN_REVIEW invoice */
app.post("/invoices/:id/approve", async (req, res) => {
  try {
    const updated = await approveInvoice(req.params.id);
    res.json(updated);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    res.status(400).json({ error: message });
  }
});

/** POST /invoices/:id/reject — mark a HUMAN_REVIEW invoice as REJECTED */
app.post("/invoices/:id/reject", (req, res) => {
  try {
    const updated = rejectInvoice(req.params.id);
    res.json(updated);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    res.status(400).json({ error: message });
  }
});

// SPA fallback — serve index.html for any non-API route
app.get("*", (_req, res) => {
  res.sendFile(resolve(ROOT, "public/index.html"));
});

// ── Start ──────────────────────────────────────────────────────────────────

const PORT = parseInt(process.env.PORT ?? "3000", 10);

app.listen(PORT, () => {
  console.log(`[SERVER] invo-frontend listening on http://localhost:${PORT}`);
  console.log(`[SERVER] Loaded ${decisions.length} decisions from ${source}`);
  console.log(`[SERVER] Serving invoice images from ${OUT_DIR} at /invoice-images`);
  console.log(`[SERVER] API: GET /invoices  POST /invoices/:id/approve|reject`);
});
