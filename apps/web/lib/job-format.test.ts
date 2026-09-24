// AJI-028 — source attribution and the origin label.
import { describe, expect, it } from "vitest";

import type { Job } from "./jobs";
import { formatJobOrigin, sourceAttributionLink } from "./job-format";

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    title: "Platform Engineer",
    company: "Initech",
    location: null,
    country: "USA",
    remote_type: null,
    employment_type: null,
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    contract_duration: null,
    contract_worker_type: null,
    description: null,
    requirements: null,
    responsibilities: null,
    posting_date: null,
    source: "some_source",
    origin: "discovered",
    is_test_data: false,
    source_url: null,
    application_url: null,
    first_seen_at: "2026-09-24T00:00:00",
    last_seen_at: "2026-09-24T00:00:00",
    ...overrides,
  };
}

const CREDITED = {
  name: "Credited Example",
  url: "https://credited.example/jobs/9",
  requires_link_back: true,
};

describe("formatJobOrigin (AJI-028)", () => {
  it("uses the registered display name when the source has one", () => {
    expect(
      formatJobOrigin(job({ source_attribution: { ...CREDITED } })),
    ).toBe("Discovered · Credited Example");
  });

  it("keeps the existing label for Greenhouse", () => {
    expect(
      formatJobOrigin(
        job({
          source: "greenhouse",
          source_attribution: {
            name: "Greenhouse",
            url: null,
            requires_link_back: false,
          },
        }),
      ),
    ).toBe("Discovered · Greenhouse");
  });

  it("falls back to the formatted source without an attribution", () => {
    expect(formatJobOrigin(job({ source_attribution: null }))).toBe(
      "Discovered · Some Source",
    );
    expect(formatJobOrigin(job())).toBe("Discovered · Some Source");
  });

  it("never credits a provider for the user's own job or test data", () => {
    expect(
      formatJobOrigin(
        job({ origin: "user_submitted", source_attribution: { ...CREDITED } }),
      ),
    ).toBe("Added by you · private");
    expect(formatJobOrigin(job({ is_test_data: true }))).toBe(
      "Synthetic · development data",
    );
  });
});

describe("sourceAttributionLink (AJI-028)", () => {
  it("links to the posting when the source requires credit", () => {
    expect(sourceAttributionLink(job({ source_attribution: CREDITED }))).toEqual({
      label: "Job via Credited Example",
      href: "https://credited.example/jobs/9",
    });
  });

  it("is null when the source does not require credit", () => {
    expect(
      sourceAttributionLink(
        job({ source_attribution: { ...CREDITED, requires_link_back: false } }),
      ),
    ).toBeNull();
  });

  it("is null without an attribution or a link", () => {
    expect(sourceAttributionLink(job())).toBeNull();
    expect(sourceAttributionLink(job({ source_attribution: null }))).toBeNull();
    expect(
      sourceAttributionLink(
        job({ source_attribution: { ...CREDITED, url: null } }),
      ),
    ).toBeNull();
  });

  it("never renders a non-http(s) link", () => {
    expect(
      sourceAttributionLink(
        job({
          source_attribution: { ...CREDITED, url: "javascript:alert(1)" },
        }),
      ),
    ).toBeNull();
  });
});
