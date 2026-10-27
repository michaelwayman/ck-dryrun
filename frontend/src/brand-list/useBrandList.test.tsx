import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { examples } from "../mocks";
import { CONFIG, respond, server } from "./test-server";
import { BrandsApiError, type ListState } from "./types";
import { useBrandList } from "./useBrandList";

const DEFAULT: ListState = {
  industries: [],
  ordering: "-average_rating",
  page: 1,
};
const DEFAULT_REQUEST = "/api/brands/?ordering=-average_rating&page_size=12";

function requests() {
  const urls: string[] = [];
  server.events.on("request:start", ({ request }) => {
    const url = new URL(request.url);
    urls.push(`${url.pathname}${url.search}`);
  });
  return urls;
}

describe("useBrandList", () => {
  it("loads the filter-sort example through the shared handlers", async () => {
    const state: ListState = {
      industries: ["insurance", "telecom"],
      ordering: "-review_count",
      page: 1,
    };
    const { result } = renderHook(() =>
      useBrandList(state, { ...CONFIG, pageSize: 1 }),
    );

    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.data).toEqual(
      examples["list-filter-sort.json"]!.response.body,
    );
  });

  it("turns an error body into a typed error", async () => {
    respond(
      "/api/brands/?ordering=-average_rating&page=9&page_size=12",
      "list-page-out-of-range.json",
    );
    const { result } = renderHook(() =>
      useBrandList({ ...DEFAULT, page: 9 }, CONFIG),
    );

    await waitFor(() => expect(result.current.status).toBe("error"));
    const error = result.current.error!;
    expect(error).toBeInstanceOf(BrandsApiError);
    expect([error.status, error.code, error.message]).toEqual([
      404,
      "not_found",
      "Page out of range.",
    ]);
  });

  it("aborts the in-flight request when the view changes", async () => {
    const abort = vi.spyOn(AbortController.prototype, "abort");
    const urls = requests();
    respond(DEFAULT_REQUEST, "list-default.json");
    respond(
      "/api/brands/?industry=retail&ordering=-average_rating&page_size=12",
      "list-empty.json",
    );
    const { result, rerender } = renderHook(
      ({ state }) => useBrandList(state, CONFIG),
      { initialProps: { state: DEFAULT } },
    );
    rerender({ state: { ...DEFAULT, industries: ["retail"] } });

    expect(abort).toHaveBeenCalled();
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.data?.count).toBe(0);
    expect(urls.at(-1)).toBe(
      "/api/brands/?industry=retail&ordering=-average_rating&page_size=12",
    );
    abort.mockRestore();
  });

  it("requests again on retry", async () => {
    const urls = requests();
    respond(DEFAULT_REQUEST, "list-default.json");
    const { result } = renderHook(() => useBrandList(DEFAULT, CONFIG));
    await waitFor(() => expect(result.current.status).toBe("success"));

    act(() => result.current.retry());

    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(urls.filter((u) => u === DEFAULT_REQUEST)).toHaveLength(2);
  });
});
