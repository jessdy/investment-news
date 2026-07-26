import type {EtfDashboard, NewsData, RefreshStatus, WechatContent} from "./types";

async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {cache: "no-store", signal});
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as {error?: string} | null;
    throw new Error(payload?.error || `请求失败（HTTP ${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export function fetchDashboard(signal?: AbortSignal) {
  return Promise.all([
    fetchJson<NewsData>("/api/news", signal),
    fetchJson<WechatContent>("/api/wechat-articles", signal),
  ]);
}

export function fetchRefreshStatus(signal?: AbortSignal) {
  return fetchJson<RefreshStatus>("/api/refresh-status", signal);
}

export function fetchEtfDashboard(
  range?: {startDate: string; endDate: string},
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  if (range?.startDate) params.set("start_date", range.startDate);
  if (range?.endDate) params.set("end_date", range.endDate);
  const query = params.size ? `?${params.toString()}` : "";
  return fetchJson<EtfDashboard>(`/api/etf-shares${query}`, signal);
}
