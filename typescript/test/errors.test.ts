import { describe, expect, it } from "vitest";
import { classifyError, ClassifiedError, ValidationFailure, AuthFailure } from "../src/harness/errors.js";

describe("error classification", () => {
  it("honors an explicitly classified error and derives retryable from type", () => {
    expect(classifyError(new ClassifiedError("transient", "boom"))).toMatchObject({ type: "transient", retryable: true });
    expect(classifyError(new ValidationFailure("bad input"))).toMatchObject({ type: "validation", retryable: false });
    expect(classifyError(new AuthFailure("nope"))).toMatchObject({ type: "auth", retryable: false });
  });

  it("classifies HTTP-status-bearing errors", () => {
    expect(classifyError({ status: 429, message: "slow down" }).type).toBe("transient");
    expect(classifyError({ status: 503, message: "down" }).type).toBe("transient");
    expect(classifyError({ status: 401, message: "no" }).type).toBe("auth");
    expect(classifyError({ status: 422, message: "bad" }).type).toBe("validation");
    expect(classifyError({ status: 404, message: "gone" }).type).toBe("permanent");
  });

  it("classifies from message text when no status is present", () => {
    expect(classifyError(new Error("Connection reset by peer")).type).toBe("transient");
    expect(classifyError(new Error("rate limit exceeded")).type).toBe("transient");
    expect(classifyError(new Error("permission denied")).type).toBe("auth");
  });

  it("defaults an unknown error to permanent (surface-as-final, never loop)", () => {
    const classified = classifyError(new Error("something unexpected happened"));
    expect(classified.type).toBe("permanent");
    expect(classified.retryable).toBe(false);
  });

  it("only transient is ever retryable", () => {
    for (const type of ["permanent", "validation", "auth"] as const) {
      expect(classifyError(new ClassifiedError(type, "x")).retryable).toBe(false);
    }
    expect(classifyError(new ClassifiedError("transient", "x")).retryable).toBe(true);
  });
});
