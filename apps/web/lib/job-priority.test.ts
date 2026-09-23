// AJI-025 — the Priority API client and its display helpers.
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./auth", () => ({ getAuthToken: () => "token-123" }));

import {
  PRIORITY_STATE_DISPLAY,
  buildJobPriorityQuery,
  formatPercent,
  getJobPriority,
  splitPriorityItems,
  type JobPriorityItem,
  type PriorityState,
} from "./job-priority";

function item(id: string, state: PriorityState): JobPriorityItem {
  return {
    job: { id } as JobPriorityItem["job"],
    rank: null,
    state,
    eligibility_status: "eligible",
    reasons: [],
    blocking_factors: [],
    inputs: {
      eligibility: {
        status: "eligible",
        engine_version: "1.0.0",
        failed_constraints: [],
        unknown_constraints: [],
      },
      job_match: null,
      ats_alignment: null,
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("buildJobPriorityQuery", () => {
  it("pins the resume version and passes the listing filters", () => {
    const query = new URLSearchParams(
      buildJobPriorityQuery({
        resumeVersionId: "version-2",
        search: "data",
        employment_type: "contract",
        remote_type: "remote",
        location: "NJ",
        page: 3,
      }),
    );

    expect(query.get("resume_version_id")).toBe("version-2");
    expect(query.get("search")).toBe("data");
    expect(query.get("employment_type")).toBe("contract");
    expect(query.get("remote_type")).toBe("remote");
    expect(query.get("location")).toBe("NJ");
    expect(query.get("page")).toBe("3");
    expect(query.get("page_size")).toBe("20");
  });

  it("omits every unset filter", () => {
    const query = new URLSearchParams(buildJobPriorityQuery({}));

    expect([...query.keys()]).toEqual(["page", "page_size"]);
  });
});

describe("getJobPriority", () => {
  it("calls the authenticated priority endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getJobPriority({ resumeVersionId: "version-1" });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/priority\?resume_version_id=version-1&/);
    expect(options.headers.Authorization).toBe("Bearer token-123");
    expect(options.cache).toBe("no-store");
  });

  it("surfaces the API's own error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Resume version not found." }),
      }),
    );

    await expect(getJobPriority({ resumeVersionId: "nope" })).rejects.toThrow(
      "Resume version not found.",
    );
  });
});

describe("splitPriorityItems", () => {
  it("splits by state without reordering the server's order", () => {
    const sections = splitPriorityItems([
      item("a", "ranked"),
      item("b", "partial"),
      item("c", "ranked"),
      item("d", "not_ready"),
      item("e", "excluded"),
    ]);

    expect(sections.ordered.map((i) => i.job.id)).toEqual(["a", "b", "c"]);
    expect(sections.notReady.map((i) => i.job.id)).toEqual(["d"]);
    expect(sections.excluded.map((i) => i.job.id)).toEqual(["e"]);
  });
});

describe("display helpers", () => {
  it("rounds like the rest of the Jobs page", () => {
    expect(formatPercent(82.5)).toBe("83%");
    expect(formatPercent(71.2)).toBe("71%");
  });

  it("labels every state without recommending anything", () => {
    for (const state of ["ranked", "partial", "not_ready", "excluded"] as const) {
      const { label } = PRIORITY_STATE_DISPLAY[state];
      expect(label).toBeTruthy();
      expect(label.toLowerCase()).not.toMatch(/recommend|best|top pick/);
    }
  });
});
