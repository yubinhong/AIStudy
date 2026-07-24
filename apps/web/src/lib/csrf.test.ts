import { describe, expect, it } from "vitest";

import { csrfHeaderFromCookie } from "./csrf";

describe("csrfHeaderFromCookie", () => {
  it("converts the session CSRF cookie into the request header", () => {
    expect(
      csrfHeaderFromCookie("study_session=session; study_csrf=csrf%20token"),
    ).toEqual({
      "X-CSRF-Token": "csrf token",
    });
  });

  it("does not add a header when the CSRF cookie is absent", () => {
    expect(csrfHeaderFromCookie("study_session=session")).toEqual({});
  });
});
