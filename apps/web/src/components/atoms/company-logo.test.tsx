import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CompanyLogo } from "@/components/atoms/company-logo";

afterEach(cleanup);

describe("CompanyLogo", () => {
  it("renders a favicon <img> for a URL logo (never the raw URL as text)", () => {
    const { container } = render(
      <CompanyLogo
        src="https://icons.duckduckgo.com/ip3/neoris.job-boards.greenhouse.io.ico"
        name="Neoris"
        className="box"
      />,
    );
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img!.getAttribute("src")).toContain("duckduckgo");
    expect(container.textContent).not.toContain("https://");
  });

  it("falls back to name initials when the favicon fails to load", () => {
    const { container } = render(
      <CompanyLogo src="https://x/broken.ico" name="Neoris" className="box" />,
    );
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("NE");
  });

  it("renders a plain (non-URL) logo as text", () => {
    render(<CompanyLogo src="MA" name="Mistral AI" className="box" />);
    expect(screen.getByText("MA")).toBeInTheDocument();
  });
});
