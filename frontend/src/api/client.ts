export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const DEFAULT_REQUEST_TIMEOUT_MS = 900_000;
const ACCESS_TOKEN_KEY = "dialogue-eval-access-token";

export function accessTokenHeaders(): Record<string, string> {
  const token = window.sessionStorage.getItem(ACCESS_TOKEN_KEY)?.trim();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function promptForAccessToken(): boolean {
  const token = window.prompt("请输入平台访问令牌")?.trim();
  if (!token) return false;
  window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
  return true;
}

async function fetchWithAccessToken(path: string, options: RequestInit): Promise<Response> {
  const doFetch = () =>
    fetch(path, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...accessTokenHeaders()
      }
    });

  let response = await doFetch();
  if (response.status === 401 && promptForAccessToken()) {
    response = await doFetch();
  }
  return response;
}

export async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), DEFAULT_REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetchWithAccessToken(path, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      ...options,
      signal: options.signal || controller.signal
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超过 15 分钟仍未返回，请降低场景数或稍后在历史评测中查看结果。", 408);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || response.statusText, response.status);
  }

  return (await response.json()) as T;
}
