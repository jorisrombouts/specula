import { describe, it, expect, vi, afterEach } from "vitest";
import type { ExportBundle } from "@specula/shared-types";

const bffFetch = vi.fn();
vi.mock("@/lib/api/bff", () => ({ bffFetch }));

const { getAccountExport, deleteAccount } = await import("@/lib/api/account");
const { GET: exportRoute } = await import("@/app/api/account/export/route");
const { DELETE: accountRoute } = await import("@/app/api/account/route");

const EXPORT_FIXTURE: ExportBundle = {
  exportedAt: "2026-07-22T00:00:00Z",
  candidate: null,
  targeting: null,
  companies: [],
  postings: [],
  scores: [],
  lenses: [],
  runs: [],
  llmCosts: [],
};

afterEach(() => {
  vi.restoreAllMocks();
  bffFetch.mockReset();
});

describe("lib/api/account data-access", () => {
  it("getAccountExport proxies GET /account/export", async () => {
    bffFetch.mockResolvedValue(EXPORT_FIXTURE);
    const bundle = await getAccountExport();
    expect(bffFetch).toHaveBeenCalledWith("/account/export");
    expect(bundle).toEqual(EXPORT_FIXTURE);
  });

  it("GET /api/account/export returns the bundle as a downloadable attachment", async () => {
    bffFetch.mockResolvedValue(EXPORT_FIXTURE);
    const res = await exportRoute();
    expect(res.headers.get("content-disposition")).toContain("attachment");
    expect(res.headers.get("content-disposition")).toContain(
      "specula-export.json",
    );
    expect(await res.json()).toEqual(EXPORT_FIXTURE);
  });

  it("DELETE /api/account proxies DELETE /account and returns 204", async () => {
    bffFetch.mockResolvedValue(undefined);
    const res = await accountRoute();
    expect(bffFetch).toHaveBeenCalledWith("/account", { method: "DELETE" });
    expect(res.status).toBe(204);
  });
});

describe("deleteAccount (client)", () => {
  it("DELETEs /api/account", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);
    await deleteAccount();
    expect(fetchMock).toHaveBeenCalledWith("/api/account", {
      method: "DELETE",
    });
  });

  it("throws on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500 }),
    );
    await expect(deleteAccount()).rejects.toThrow();
  });
});
