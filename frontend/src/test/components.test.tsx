import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buildQuery } from "../api/client";
import { ConfirmDialog, Slider, StatusBadge, TeamBadge } from "../components/ui";
import { formatDuration, formatGameTime, pct, titleCase } from "../lib/format";

describe("ui components", () => {
  it("renders status badges with readable labels", () => {
    render(<StatusBadge status="soft_support" />);
    expect(screen.getByText("Soft Support")).toBeInTheDocument();
  });

  it("renders team badge or a dash", () => {
    const { rerender } = render(<TeamBadge team="radiant" />);
    expect(screen.getByText("radiant")).toBeInTheDocument();
    rerender(<TeamBadge team={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("slider reports numeric changes", () => {
    const onChange = vi.fn();
    render(<Slider label="Aggression" value={0.5} onChange={onChange} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Aggression"), { target: { value: "0.8" } });
    expect(onChange).toHaveBeenCalledWith(0.8);
  });

  it("confirm dialog calls handlers", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="Stop?" message="sure" onConfirm={onConfirm} onCancel={onCancel} confirmLabel="Stop it" />);
    fireEvent.click(screen.getByText("Stop it"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("dialog is not rendered when closed", () => {
    render(<ConfirmDialog open={false} title="x" message="hidden" onConfirm={() => {}} onCancel={() => {}} />);
    expect(screen.queryByText("hidden")).toBeNull();
  });
});

describe("helpers", () => {
  it("formats times and labels", () => {
    expect(formatGameTime(125)).toBe("2:05");
    expect(formatGameTime(null)).toBe("—");
    expect(formatDuration(2100)).toBe("35m 00s");
    expect(titleCase("radiant_advantage")).toBe("Radiant Advantage");
    expect(pct(0.256)).toBe("26%");
    expect(pct(null)).toBe("—");
  });

  it("builds query strings and skips empty values", () => {
    expect(buildQuery({ a: 1, b: "", c: undefined, d: [1, 2] })).toBe("?a=1&d=1&d=2");
    expect(buildQuery()).toBe("");
  });
});
