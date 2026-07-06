import { describe, it, expect, vi } from "vitest";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { PATCH } = await import("@/app/api/jobs/[id]/state/route");

describe("PATCH /api/jobs/[id]/state", () => {
  it("forwards to FastAPI and returns the reconciled state", async () => {
    const req = new Request("http://localhost/api/jobs/j1/state", {
      method: "PATCH",
      body: JSON.stringify({ status: "Saved", note: "referred by Anna" }),
    });
    const res = await PATCH(req, { params: Promise.resolve({ id: "j1" }) });
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({
      status: "Saved",
      note: "referred by Anna",
    });
  });
});
