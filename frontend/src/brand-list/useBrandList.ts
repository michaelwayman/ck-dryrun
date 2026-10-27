// Loads one brands-api page for the current view. Each new request aborts the one before it, and
// a response is only kept if it answers the latest request.
import { useCallback, useEffect, useState } from "react";
import { apiRequestUrl } from "./url-state";
import {
  BrandsApiError,
  type ApiErrorBody,
  type BrandPage,
  type ListState,
  type MountConfig,
} from "./types";

export type BrandListResult =
  | { status: "loading"; data: null; error: null }
  | { status: "success"; data: BrandPage; error: null }
  | { status: "error"; data: null; error: BrandsApiError };

interface Settled {
  key: string;
  result: BrandListResult;
}

const LOADING: BrandListResult = { status: "loading", data: null, error: null };

function isErrorBody(body: unknown): body is { error: ApiErrorBody } {
  const error = (body as { error?: Partial<ApiErrorBody> } | null)?.error;
  return typeof error?.code === "string" && typeof error.message === "string";
}

async function load(url: string, signal: AbortSignal): Promise<BrandPage> {
  let response: Response;
  try {
    response = await fetch(url, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (cause) {
    if (signal.aborted) throw cause;
    throw new BrandsApiError(0, {
      code: "network_error",
      message: "The brands could not be reached.",
      fields: null,
    });
  }
  const body: unknown = await response.json().catch(() => null);
  if (response.ok) return body as BrandPage;
  throw new BrandsApiError(
    response.status,
    isErrorBody(body)
      ? body.error
      : {
          code: "http_error",
          message: `HTTP ${response.status}.`,
          fields: null,
        },
  );
}

export function useBrandList(
  state: ListState,
  config: MountConfig,
): BrandListResult & { retry: () => void } {
  const url = apiRequestUrl(state, config, window.location.href).href;
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled | null>(null);
  const key = `${attempt} ${url}`;

  useEffect(() => {
    const controller = new AbortController();
    load(url, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) {
          setSettled({
            key,
            result: { status: "success", data, error: null },
          });
        }
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        const failure =
          error instanceof BrandsApiError
            ? error
            : new BrandsApiError(0, {
                code: "bad_response",
                message: "The brands could not be read.",
                fields: null,
              });
        setSettled({
          key,
          result: { status: "error", data: null, error: failure },
        });
      },
    );
    return () => controller.abort();
  }, [key, url]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const result = settled?.key === key ? settled.result : LOADING;
  return { ...result, retry };
}
