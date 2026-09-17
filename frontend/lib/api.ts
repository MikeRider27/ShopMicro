import type { Category, Order, Product, User } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export class ApiError extends Error {
  code?: string;
  status?: number;

  constructor(message: string, code?: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    // Correlation ID: viaja hasta cada microservicio (ver nginx.conf y
    // middleware.py en cada servicio) para poder seguir un mismo request en
    // los logs de todos ellos.
    "X-Request-ID": crypto.randomUUID(),
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers, cache: "no-store" });
  } catch {
    // fetch() rechaza por error de red (servidor caído, sin conexión, CORS),
    // no por un status HTTP de error. Sin este catch, el mensaje que le
    // llegaría al usuario sería el críptico "Failed to fetch".
    throw new ApiError("No se pudo conectar con el servidor. Revisá tu conexión e intentá de nuevo.");
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    if (res.status === 401 && token) {
      // Sesión inválida o expirada: limpiar y forzar un nuevo login,
      // explicando por qué en vez de mandarlo en silencio a /login.
      try {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
      } catch {
        // ignore
      }
      if (typeof window !== "undefined") {
        window.location.href = "/login?reason=session_expired";
      }
      throw new ApiError("Tu sesión expiró. Inicia sesión de nuevo.", "SESSION_EXPIRED", 401);
    }
    const errorBody = typeof data.error === "object" ? data.error : { message: data.error };
    throw new ApiError(errorBody?.message || `Error ${res.status}`, errorBody?.code, res.status);
  }
  return data as T;
}

export const api = {
  // Auth
  register: (payload: { email: string; password: string; name: string }) =>
    request<{ user: User; access_token: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  login: (payload: { email: string; password: string }) =>
    request<{ user: User; access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  me: (token: string) => request<{ user: User }>("/api/auth/me", {}, token),

  // Products
  listProducts: (params?: { category?: string; search?: string }) => {
    const cleaned: Record<string, string> = {};
    if (params?.category) cleaned.category = params.category;
    if (params?.search) cleaned.search = params.search;
    const query = new URLSearchParams(cleaned).toString();
    return request<{ products: Product[] }>(`/api/products/products${query ? `?${query}` : ""}`);
  },
  getProduct: (id: number) => request<{ product: Product }>(`/api/products/products/${id}`),
  listCategories: () => request<{ categories: Category[] }>("/api/products/categories"),

  // Orders
  createOrder: (
    payload: { items: { product_id: number; quantity: number }[]; shipping_address: string },
    token: string,
    idempotencyKey: string
  ) =>
    request<{ order: Order }>(
      "/api/orders/orders",
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Idempotency-Key": idempotencyKey },
      },
      token
    ),
  listOrders: (token: string) => request<{ orders: Order[] }>("/api/orders/orders", {}, token),
};
