import { describe, it, expect } from "vitest";
import { PATCH } from "@/app/api/jobs/[id]/state/route";

describe("PATCH /api/jobs/[id]/state", () => {
  it("echoes the patch back for optimistic reconcile", async () => {
    const req = new Request("http://localhost/api/jobs/j1/state", {
      method: "PATCH",
      body: JSON.stringify({ status: "Saved", note: "referred by Anna" }),
    });
    const res = await PATCH(req, { params: Promise.resolve({ id: "j1" }) });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      status: "Saved",
      note: "referred by Anna",
    });
  });
});
