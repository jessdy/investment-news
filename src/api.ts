import type {
  AuthUser,
  EtfDashboard,
  NewsData,
  RefreshStatus,
  WechatContent,
  WechatLoginStatus,
  WechatLoginTicket,
} from "./types";

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

export async function createWechatLoginTicket() {
  const response = await fetch("/api/auth/wechat/ticket", {
    method: "POST",
    cache: "no-store",
    credentials: "same-origin",
  });
  const payload = await response.json().catch(() => null) as
    | (WechatLoginTicket & {error?: string})
    | null;
  if (!response.ok || !payload) {
    throw new Error(payload?.error || "无法生成微信登录二维码");
  }
  return payload;
}

export function pollWechatLogin(ticket: string, signal?: AbortSignal) {
  return fetchJson<WechatLoginStatus>(
    `/api/auth/wechat/status?ticket=${encodeURIComponent(ticket)}`,
    signal,
  );
}

export async function fetchCurrentUser(signal?: AbortSignal) {
  const response = await fetch("/api/auth/me", {
    cache: "no-store",
    credentials: "same-origin",
    signal,
  });
  if (response.status === 401) return null;
  const payload = await response.json().catch(() => null) as
    | {authenticated: boolean; user?: AuthUser; error?: string}
    | null;
  if (!response.ok) {
    throw new Error(payload?.error || "无法读取登录状态");
  }
  return payload?.user ?? null;
}

export async function logoutWechat() {
  const response = await fetch("/api/auth/logout", {
    method: "POST",
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error("退出登录失败");
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
