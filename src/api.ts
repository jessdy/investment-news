import type {NewsData, RefreshStatus, WechatContent} from "./types";

async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {cache: "no-store", signal});
  if (!response.ok) {
    throw new Error(`请求失败（HTTP ${response.status}）`);
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
