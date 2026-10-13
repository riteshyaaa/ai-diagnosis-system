// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { CaseModality, type CaseReportPreview } from "../../types";
import { describe, expect, it, vi } from "vitest";
import { CaseReportPreviewPanel } from "./CaseReportPreviewPanel";

const report: CaseReportPreview = {
  case_id: "case-1",
  case_reference: "CASE-REPORT-1",
  generated_at: "2026-10-13T12:00:00Z",
  status: "DRAFT",
  modality: CaseModality.TABULAR_ONLY,
  patient: { age: 54, sex: "female" },
  clinical_input: null,
  image_input: null,
  prediction: {
    id: "prediction-1",
    model_type: "tabular_mlp",
    model_version: "1.0.0",
    model_reported_finding: "model-reported finding",
    raw_score: 0.7,
    stored_probability: 0.65,
    confidence_score: 0.6,
    confidence_band: "low",
    status: "uncertain",
    input_version_current: false,
    created_at: "2026-10-13T11:00:00Z",
  },
  review: null,
  free_text_notes_included: false,
  probability_notice: "Stored scores are not verified as calibrated probabilities.",
  disclaimer: "This preview is not a finalized report.",
};

describe("CaseReportPreviewPanel", () => {
  it("labels stale model output and exposes a close action", () => {
    const onClose = vi.fn();
    render(<CaseReportPreviewPanel report={report} onClose={onClose} />);

    expect(screen.getByText("Draft report preview")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("shown as stale history");
    expect(screen.getByText(report.probability_notice)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Close report preview" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
