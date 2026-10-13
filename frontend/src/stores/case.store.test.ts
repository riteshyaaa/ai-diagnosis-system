import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getCaseById: vi.fn(),
  getExplanationByPredictionId: vi.fn(),
  predictCase: vi.fn(),
}));

vi.mock("../services/cases.service", () => ({
  caseService: { getCaseById: mocks.getCaseById },
}));
vi.mock("../services/explanations.service", () => ({
  explanationService: {
    getExplanationByPredictionId: mocks.getExplanationByPredictionId,
  },
}));
vi.mock("../services/predictions.service", () => ({
  predictionService: { predictCase: mocks.predictCase },
}));

import { predictionMatchesCurrentInputs, useCaseStore } from "./case.store";
import type { DiagnosticCaseDetail, PredictionResponse } from "../types";

const caseFixture = {
  id: "case-1",
  images: [
    {
      id: "image-1",
      file_hash: "sha256-image-a",
      created_at: "2026-10-01T10:00:00Z",
    },
  ],
  clinical_records: [
    {
      id: "clinical-1",
      created_at: "2026-10-01T10:01:00Z",
      updated_at: "2026-10-01T10:05:00Z",
    },
  ],
  predictions: [],
} as unknown as DiagnosticCaseDetail;

const predictionFixture = {
  id: "prediction-1",
  image_record_id: "image-1",
  image_file_hash: "sha256-image-a",
  clinical_record_id: "clinical-1",
  clinical_record_updated_at: "2026-10-01T10:05:00Z",
} as PredictionResponse;

describe("case store input-version safety", () => {
  beforeEach(() => {
    mocks.getCaseById.mockReset();
    mocks.getExplanationByPredictionId.mockReset();
    mocks.predictCase.mockReset();
    useCaseStore.setState({
      selectedCase: null,
      activePrediction: null,
      activeExplanation: null,
      isLoading: false,
      isPredicting: false,
      error: null,
    });
  });

  it("accepts a prediction only when both input versions match", () => {
    expect(predictionMatchesCurrentInputs(caseFixture, predictionFixture)).toBe(true);
    expect(
      predictionMatchesCurrentInputs(caseFixture, {
        ...predictionFixture,
        image_file_hash: "sha256-image-b",
      }),
    ).toBe(false);
    expect(
      predictionMatchesCurrentInputs(caseFixture, {
        ...predictionFixture,
        clinical_record_updated_at: "2026-10-01T10:06:00Z",
      }),
    ).toBe(false);
    expect(
      predictionMatchesCurrentInputs(caseFixture, {
        ...predictionFixture,
        clinical_record_id: null,
        clinical_record_updated_at: null,
      }),
    ).toBe(false);
  });

  it("hides a saved prediction when the case inputs changed", async () => {
    mocks.getCaseById.mockResolvedValue({
      ...caseFixture,
      predictions: [
        { ...predictionFixture, image_record_id: "older-image" },
      ],
    });

    await useCaseStore.getState().loadCase("case-1");

    expect(useCaseStore.getState().activePrediction).toBeNull();
    expect(useCaseStore.getState().activeExplanation).toBeNull();
  });

  it("keeps model-unavailable errors visible and clears the loading state", async () => {
    mocks.predictCase.mockRejectedValue({
      response: { data: { detail: "No verified model is available." } },
    });

    await expect(useCaseStore.getState().runPrediction("case-1")).rejects.toBeTruthy();

    expect(useCaseStore.getState().isPredicting).toBe(false);
    expect(useCaseStore.getState().error).toBe("No verified model is available.");
  });
});
