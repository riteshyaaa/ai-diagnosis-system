import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("./api", () => ({ default: { get: mocks.get } }));

import { caseService } from "./cases.service";

describe("caseService", () => {
  beforeEach(() => mocks.get.mockReset().mockResolvedValue({ data: {} }));

  it("loads the case detail endpoint used by the workstation", async () => {
    await caseService.getCaseById("case-123");

    expect(mocks.get).toHaveBeenCalledWith("/cases/case-123/details");
  });

  it("loads the protected report preview endpoint", async () => {
    await caseService.getReportPreview("case-123");

    expect(mocks.get).toHaveBeenCalledWith("/cases/case-123/report-preview");
  });
});
