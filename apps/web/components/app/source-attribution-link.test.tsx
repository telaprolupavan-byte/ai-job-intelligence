// @vitest-environment jsdom
//
// AJI-028 — the visible source credit ("Job via X") a source's terms can
// require, rendered only when the API says it is required.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";

import type { Job } from "@/lib/jobs";
import SourceAttributionLink from "./source-attribution-link";

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
    source: "credited_example",
    origin: "discovered",
    is_test_data: false,
    source_url: "https://credited.example/jobs/9",
    application_url: null,
    first_seen_at: "2026-09-24T00:00:00",
    last_seen_at: "2026-09-24T00:00:00",
    ...overrides,
  };
}

describe("SourceAttributionLink (AJI-028)", () => {
  afterEach(() => cleanup());

  it("renders a safe external link naming the source", () => {
    render(
      <SourceAttributionLink
        job={job({
          source_attribution: {
            name: "Credited Example",
            url: "https://credited.example/jobs/9",
            requires_link_back: true,
          },
        })}
      />,
    );

    const link = screen.getByRole("link", { name: "Job via Credited Example" });
    expect(link).toHaveAttribute("href", "https://credited.example/jobs/9");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders nothing when the source does not require credit", () => {
    const { container } = render(
      <SourceAttributionLink
        job={job({
          source_attribution: {
            name: "Greenhouse",
            url: "https://boards.greenhouse.io/x/jobs/1",
            requires_link_back: false,
          },
        })}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing without an attribution", () => {
    const { container } = render(<SourceAttributionLink job={job()} />);

    expect(container).toBeEmptyDOMElement();
  });
});
