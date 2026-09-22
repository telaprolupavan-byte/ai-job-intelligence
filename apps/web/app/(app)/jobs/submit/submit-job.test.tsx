// @vitest-environment jsdom
//
// AJI-022 — Submit Job states (Figma 133:72 default, 133:164 analyzing,
// 133:197 error). The states are nothing more than the lifecycle of one
// POST /jobs/submissions request.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const submitJob = vi.fn();

vi.mock("@/lib/jobs", () => ({
  submitJob: (...args: unknown[]) => submitJob(...args),
}));

import SubmitJobPage from "./page";

function fillForm() {
  fireEvent.change(screen.getByLabelText("Job title"), {
    target: { value: "Senior Backend Engineer" },
  });
  fireEvent.change(screen.getByLabelText("Company"), {
    target: { value: "Acme" },
  });
  fireEvent.change(screen.getByLabelText("Job description"), {
    target: { value: "Requirements\n- 5+ years of Python" },
  });
}

function submit() {
  fireEvent.submit(screen.getByLabelText("Job description").closest("form")!);
}

describe("Submit Job page", () => {
  beforeEach(() => {
    push.mockReset();
    submitJob.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the default state with an idle NERO", () => {
    render(<SubmitJobPage />);

    expect(
      screen.getByText("Add a job for NERO to understand"),
    ).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "NERO: Idle" })).toBeInTheDocument();
    expect(
      screen.getByText("Your submitted job is private to your NERO account."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze job" })).toBeEnabled();
    expect(screen.getByLabelText("Job description")).toBeRequired();
  });

  it("shows the analyzing state while the request is in flight, then opens the analyzed job", async () => {
    let resolve!: (value: unknown) => void;
    submitJob.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );

    render(<SubmitJobPage />);
    fillForm();
    submit();

    expect(await screen.findByText("NERO is analyzing the job")).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "NERO: Analyzing" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("NERO is analyzing the submitted job content…"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();
    expect(screen.getByLabelText("Job title")).toBeDisabled();

    expect(submitJob).toHaveBeenCalledWith({
      content: "Requirements\n- 5+ years of Python",
      title: "Senior Backend Engineer",
      company: "Acme",
    });

    resolve({ job: { id: "job-123" } });

    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs?job=job-123"));
  });

  it("shows the error state, keeps the pasted content, and retries", async () => {
    submitJob.mockRejectedValueOnce(new Error("503"));

    render(<SubmitJobPage />);
    fillForm();
    submit();

    expect(
      await screen.findByText("We couldn’t understand this job"),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Analysis unavailable");
    // The user's paste is still there to review and resubmit.
    expect(screen.getByLabelText("Job description")).toHaveValue(
      "Requirements\n- 5+ years of Python",
    );
    expect(push).not.toHaveBeenCalled();

    submitJob.mockResolvedValueOnce({ job: { id: "job-456" } });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs?job=job-456"));
    expect(submitJob).toHaveBeenCalledTimes(2);
  });
});
