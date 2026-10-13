import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock("./api", () => ({ default: { get: mocks.get, post: mocks.post } }));

import { explanationService } from "./explanations.service";

describe("explanationService API contracts", () => {
  beforeEach(() => {
    mocks.get.mockReset().mockResolvedValue({ data: {} });
    mocks.post.mockReset().mockResolvedValue({ data: {} });
  });

  it("reads visual attribution from the stored explanation endpoint", async () => {
    const visual = { prediction_id: "prediction-1", attention_regions: [] };
    mocks.get.mockResolvedValueOnce({ data: { visual_explanation: visual } });

    await expect(explanationService.getGradCam("prediction-1")).resolves.toEqual(visual);
    expect(mocks.get).toHaveBeenCalledWith("/predictions/prediction-1/explanation");
  });

  it("reports visual attribution as unavailable when the response omits it", async () => {
    await expect(explanationService.getGradCam("prediction-1")).rejects.toThrow(
      "Visual attribution is unavailable",
    );
  });

  it("uses the backend feature-attribution route", async () => {
    await explanationService.getShapAttributions("prediction-1");

    expect(mocks.get).toHaveBeenCalledWith("/predictions/prediction-1/features");
  });

  it("uses the backend alternate-attribution route", async () => {
    const request = { target_pathology: "Cardiomegaly" };

    await explanationService.recalculatePathologySaliency("prediction-1", request);

    expect(mocks.post).toHaveBeenCalledWith(
      "/predictions/prediction-1/explain-pathology",
      request,
    );
  });
});
