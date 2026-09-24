// @vitest-environment jsdom
//
// AJI-030 — a development-dataset job tracked through the existing
// Applications workflow is always labelled as test data, on the list and
// on the detail view, and nothing else about the workflow changes.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

import type { Application, ApplicationDetail } from "@/lib/applications";

// A stable router, as Next provides: both pages list it as an effect
// dependency, so a new object per render would reload them forever.
const router = { replace: vi.fn(), push: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useParams: () => ({ id: "app-dev" }),
}));

const getApplications = vi.fn();
const getApplicationDetail = vi.fn();

vi.mock("@/lib/applications", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/applications")>()),
  getApplications: () => getApplications(),
  getApplicationDetail: (...args: unknown[]) => getApplicationDetail(...args),
}));

import ApplicationsPage from "./page";
import ApplicationDetailPage from "./[id]/page";

function application(
  id: string,
  title: string,
  isTestData: boolean,
): Application {
  return {
    id,
    job: {
      id: `job-${id}`,
      title,
      company: isTestData ? "Cedar & Pine Commerce (demo)" : "Initech",
      location: "New York, NY",
      employment_type: "full_time",
      remote_type: "onsite",
      application_url: null,
      is_test_data: isTestData,
    },
    status: "applied",
    applied_at: "2026-09-24T12:00:00",
    created_at: "2026-09-24T10:00:00",
    updated_at: "2026-09-24T12:00:00",
  };
}

describe("Applications (AJI-030 development data)", () => {
  beforeEach(() => {
    getApplications.mockReset();
    getApplicationDetail.mockReset();
  });

  afterEach(() => cleanup());

  it("labels only the development-data application as Test data", async () => {
    getApplications.mockResolvedValue([
      application("app-dev", "Frontend Engineer", true),
      application("app-real", "Backend Engineer", false),
    ]);

    render(<ApplicationsPage />);

    const devCard = (await screen.findByText("Frontend Engineer")).closest(
      "a",
    )!;
    const realCard = screen.getByText("Backend Engineer").closest("a")!;

    expect(within(devCard).getByText("Test data")).toBeInTheDocument();
    expect(within(devCard).getByText("Applied")).toBeInTheDocument();
    expect(within(realCard).queryByText("Test data")).not.toBeInTheDocument();
  });

  it("labels the detail view of a development-data application", async () => {
    const detail: ApplicationDetail = {
      ...application("app-dev", "Frontend Engineer", true),
      status_history: [
        { status: "saved", created_at: "2026-09-24T10:00:00" },
        { status: "applied", created_at: "2026-09-24T12:00:00" },
      ],
    };
    getApplicationDetail.mockResolvedValue(detail);

    render(<ApplicationDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Frontend Engineer" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Test data")).toBeInTheDocument();
  });
});
