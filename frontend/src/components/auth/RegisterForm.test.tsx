// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  register: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("../../stores/auth.store", () => ({
  useAuthStore: () => ({
    register: mocks.register,
    isLoading: false,
    error: null,
  }),
}));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

import { RegisterForm } from "./RegisterForm";

describe("RegisterForm", () => {
  beforeEach(() => {
    mocks.register.mockReset().mockResolvedValue(undefined);
    mocks.navigate.mockReset();
  });

  it("submits only the public clinician registration fields", async () => {
    render(
      <MemoryRouter>
        <RegisterForm />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Full Medical Name & Title"), {
      target: { value: "Taylor Example" },
    });
    fireEvent.change(screen.getByLabelText("Institutional Email"), {
      target: { value: "taylor@example.org" },
    });
    fireEvent.change(screen.getByLabelText("Department (optional)"), {
      target: { value: "Radiology" },
    });
    fireEvent.change(screen.getByLabelText("Authorization Password"), {
      target: { value: "StrongPassword2026!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "StrongPassword2026!" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Complete Staff Enrollment" }));

    await waitFor(() => {
      expect(mocks.register).toHaveBeenCalledWith({
        full_name: "Taylor Example",
        email: "taylor@example.org",
        password: "StrongPassword2026!",
        department: "Radiology",
      });
    });
    expect(screen.queryByLabelText("Clinical Role")).toBeNull();
    expect(mocks.navigate).toHaveBeenCalledWith("/cases");
  });
});
