import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { LensEditor } from "@/components/profiles/lens-editor";

afterEach(cleanup);

const lens = {
  name: "Spain",
  scope: "ES",
  modes: ["Remote", "Hybrid"] as ("Remote" | "Hybrid" | "On-site")[],
  origin: "foreign_hq",
  focus: "Barcelona",
  seeds: ["ml engineer Barcelona"],
  active: true,
};

describe("LensEditor", () => {
  it("saves the edited fields with the scope serialized and origin value", () => {
    const onSave = vi.fn();
    render(
      <LensEditor
        lens={lens}
        onSave={onSave}
        onCancel={() => {}}
        onDelete={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("profile name"), {
      target: { value: "Iberia" },
    });
    fireEvent.click(screen.getByText("Save profile"));
    expect(onSave).toHaveBeenCalledTimes(1);
    const patch = onSave.mock.calls[0][0];
    expect(patch.name).toBe("Iberia");
    expect(patch.scope).toBe("ES"); // Country -> serialized code
    expect(patch.origin).toBe("foreign_hq");
    expect(patch.short).toBe("Iberia");
  });

  it("switching scope type swaps the value control (Country select -> City text)", () => {
    render(
      <LensEditor
        lens={lens}
        onSave={() => {}}
        onCancel={() => {}}
        onDelete={() => {}}
      />,
    );
    expect(screen.getByLabelText("scope value")).toBeInTheDocument(); // Country select
    fireEvent.change(screen.getByLabelText("scope type"), {
      target: { value: "City" },
    });
    fireEvent.change(screen.getByLabelText("scope value"), {
      target: { value: "Madrid, ES" },
    });
    // Save and confirm the City value serializes through
    const onSave = vi.fn();
    cleanup();
    render(
      <LensEditor
        lens={lens}
        onSave={onSave}
        onCancel={() => {}}
        onDelete={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("scope type"), {
      target: { value: "City" },
    });
    fireEvent.change(screen.getByLabelText("scope value"), {
      target: { value: "Madrid, ES" },
    });
    fireEvent.click(screen.getByText("Save profile"));
    expect(onSave.mock.calls[0][0].scope).toBe("Madrid, ES");
  });

  it("fires onCancel and onDelete", () => {
    const onCancel = vi.fn();
    const onDelete = vi.fn();
    render(
      <LensEditor
        lens={lens}
        onSave={() => {}}
        onCancel={onCancel}
        onDelete={onDelete}
      />,
    );
    fireEvent.click(screen.getByText("Cancel"));
    fireEvent.click(screen.getByText("Delete"));
    expect(onCancel).toHaveBeenCalled();
    expect(onDelete).toHaveBeenCalled();
  });

  it("gates Save on dirty (disabled when clean, enabled after an edit)", () => {
    render(
      <LensEditor
        lens={lens}
        onSave={() => {}}
        onCancel={() => {}}
        onDelete={() => {}}
      />,
    );
    const save = screen.getByText("Save profile");
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("focus"), {
      target: { value: "Madrid, Barcelona" },
    });
    expect(save).not.toBeDisabled();
  });
});
