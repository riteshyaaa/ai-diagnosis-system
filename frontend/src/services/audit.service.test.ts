import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("./api", () => ({ default: { get: mocks.get } }));

import { auditService } from "./audit.service";

describe("auditService", () => {
  beforeEach(() => mocks.get.mockReset().mockResolvedValue({ data: { items: [], total: 0 } }));

  it("requests the real paginated audit-events endpoint with filters", async () => {
    await auditService.listEvents({ resource_type: "case", skip: 25, limit: 25 });

    expect(mocks.get).toHaveBeenCalledWith("/audit-events", {
      params: { resource_type: "case", skip: 25, limit: 25 },
    });
  });
});
