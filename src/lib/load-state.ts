/**
 * A discriminated union describing the async data we load on a page.
 * Pages reduce to one of these four states and render accordingly.
 */
export type LoadState<T> =
  | { type: "loading" }
  | { type: "error"; message: string }
  | { type: "empty" }
  | { type: "data"; data: T };

export const loadingState = (): LoadState<never> => ({ type: "loading" });
export const errorState = (message: string): LoadState<never> => ({
  type: "error",
  message,
});
export const emptyState = (): LoadState<never> => ({ type: "empty" });
export const dataState = <T,>(data: T): LoadState<T> => ({ type: "data", data });