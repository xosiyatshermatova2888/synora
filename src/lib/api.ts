// Typed API client for the SYNORA FastAPI backend.
//
// Auth strategy (mirrors backend Section 8):
//   - access token is a short-lived JWT kept ONLY in memory (never
//     localStorage/sessionStorage/IndexedDB).
//   - the refresh token lives in an httpOnly cookie scoped to /api/v1/auth.
//   - on a 401 from a non-auth endpoint we silently refresh once (POST
//     /api/v1/auth/refresh) and retry the original request. Concurrent 401s
//     share a single in-flight refresh.

const API_BASE = "/api"; // proxied by next.config.ts rewrites to the backend.

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearSession(): void {
  accessToken = null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  /** Endpoints that must never trigger the silent-refresh loop. */
  skipRefresh?: boolean;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0] as { msg?: string };
      if (first && typeof first.msg === "string") return first.msg;
    }
  } catch {
    // Not JSON; fall through to status text.
  }
  return res.statusText || `Request failed (${res.status}).`;
}

function shouldSkipRefresh(path: string): boolean {
  return path.startsWith("/api/v1/auth/");
}

async function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = fetch(`${API_BASE}/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then(async (res) => {
      if (!res.ok) {
        accessToken = null;
        return false;
      }
      const data = (await res.json()) as TokenResponse;
      accessToken = data.access_token;
      return true;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

async function request<T>(
  path: string,
  { method = "GET", body, headers, skipRefresh = false }: RequestOptions = {}
): Promise<T> {
  const finalPath = `${API_BASE}${path}`;
  const send = async (token: string | null): Promise<Response> => {
    const init: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    };
    if (body !== undefined) init.body = JSON.stringify(body);
    return fetch(finalPath, init);
  };

  let res = await send(accessToken);

  if (res.status === 401 && !skipRefresh && !shouldSkipRefresh(path)) {
    const refreshed = await refreshSession();
    if (refreshed) {
      res = await send(accessToken);
    } else {
      throw new ApiError(401, await parseError(res));
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res));
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// API contract types (mirror backend schemas exactly)
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
  restaurant_name: string;
  currency?: string;
  timezone?: string;
}

export interface RoleOut {
  id: string;
  name: string;
}

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  restaurant_id: string;
  restaurant_name: string;
  roles: RoleOut[];
  permissions: string[];
}

// --- Restaurant / Branch ---------------------------------------------------
export interface RestaurantOut {
  id: string;
  name: string;
  slug: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  timezone: string;
  currency: string;
  status: string;
  is_active: boolean;
}

export interface BranchOut {
  id: string;
  restaurant_id: string;
  name: string;
  address: string | null;
  phone: string | null;
  timezone: string | null;
  currency: string | null;
  is_active: boolean;
}

// --- Menu ------------------------------------------------------------------
export interface ModifierOut {
  id: string;
  name: string;
  price: string;
  sort_order: number;
  is_active: boolean;
}

export interface ModifierGroupOut {
  id: string;
  name: string;
  is_required: boolean;
  min_selections: number;
  max_selections: number;
  is_active: boolean;
  modifiers: ModifierOut[];
}

export interface ProductOut {
  id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  price: string;
  cost_price: string;
  image_url: string | null;
  is_available: boolean;
  is_active: boolean;
  modifier_groups: ModifierGroupOut[];
}

export interface CategoryOut {
  id: string;
  restaurant_id: string;
  name: string;
  description: string | null;
  image_url: string | null;
  sort_order: number;
  is_active: boolean;
  products: ProductOut[];
}

export interface CategoryCreate {
  name: string;
  description?: string | null;
  image_url?: string | null;
  sort_order?: number;
}

export interface CategoryUpdate {
  name?: string;
  description?: string | null;
  image_url?: string | null;
  sort_order?: number;
  is_active?: boolean;
}

export interface ProductCreate {
  category_id?: string | null;
  name: string;
  description?: string | null;
  price: string;
  cost_price?: string;
  image_url?: string | null;
  is_available?: boolean;
  modifier_group_ids?: string[];
}

export interface ProductUpdate {
  category_id?: string | null;
  name?: string;
  description?: string | null;
  price?: string;
  cost_price?: string;
  image_url?: string | null;
  is_available?: boolean;
  is_active?: boolean;
}

// --- Tables ----------------------------------------------------------------
export interface TableOut {
  id: string;
  restaurant_id: string;
  branch_id: string;
  name: string;
  capacity: number;
  status: string;
  is_active: boolean;
  version: number;
}

export interface TableCreate {
  branch_id: string;
  name: string;
  capacity?: number;
}

export interface TableUpdate {
  name?: string;
  capacity?: number;
  status?: string;
  is_active?: boolean;
}

// --- Orders ----------------------------------------------------------------
export interface OrderModifierSelection {
  modifier_id: string;
  quantity?: number;
}

export interface OrderItemIn {
  product_id: string;
  quantity?: number;
  notes?: string;
  modifiers?: OrderModifierSelection[];
}

export interface OrderCreate {
  branch_id: string;
  table_id?: string | null;
  source?: string;
  notes?: string;
  discount?: string;
  items: OrderItemIn[];
}

export interface OrderItemModifierOut {
  id: string;
  modifier_name_snapshot: string;
  price: string;
  quantity: number;
}

export interface OrderItemOut {
  id: string;
  product_id: string | null;
  product_name_snapshot: string;
  unit_price: string;
  quantity: number;
  discount: string;
  notes: string | null;
  modifiers: OrderItemModifierOut[];
}

export interface OrderOut {
  id: string;
  restaurant_id: string;
  branch_id: string;
  table_id: string | null;
  order_number: number;
  status: string;
  kitchen_status: string;
  source: string;
  subtotal: string;
  discount: string;
  tax: string;
  service_charge: string;
  total: string;
  currency: string;
  notes: string | null;
  waiter_user_id: string | null;
  created_by_user_id: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  items: OrderItemOut[];
  created_at: string;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- Payments --------------------------------------------------------------
export interface PaymentOut {
  id: string;
  order_id: string;
  amount: string;
  method: string;
  status: string;
  reference: string | null;
  created_at: string;
}

export interface PaymentCreate {
  order_id: string;
  amount: string;
  method?: string;
  reference?: string | null;
}

export interface CashShiftOut {
  id: string;
  branch_id: string;
  cashier_user_id: string | null;
  opened_at: string;
  closed_at: string | null;
  opening_balance: string;
  expected_closing_balance: string | null;
  actual_closing_balance: string | null;
  status: string;
  version: number;
}

// --- Kitchen ---------------------------------------------------------------
export type KitchenTicketStatus = "NEW" | "PREPARING" | "READY" | "SERVED";

export interface KitchenTicketItemModifierOut {
  modifier_name_snapshot: string;
  quantity: number;
}

export interface KitchenTicketItemOut {
  product_name_snapshot: string;
  quantity: number;
  notes: string | null;
  modifiers: KitchenTicketItemModifierOut[];
}

export interface KitchenTicketOut {
  id: string;
  restaurant_id: string;
  branch_id: string;
  order_id: string;
  order_number: number;
  table_name: string | null;
  station_id: string | null;
  status: KitchenTicketStatus;
  notes: string | null;
  source: string;
  items: KitchenTicketItemOut[];
  created_at: string;
  updated_at: string;
}

export interface KitchenStationOut {
  id: string;
  restaurant_id: string;
  branch_id: string;
  name: string;
  is_active: boolean;
}

export interface KitchenStationCreate {
  branch_id: string;
  name: string;
}

export type KitchenEventName =
  | "order_sent_to_kitchen"
  | "order_preparing"
  | "order_ready"
  | "order_served"
  | "ticket_removed";

export interface KitchenEvent {
  event: KitchenEventName;
  order_id?: string;
  branch_id?: string;
  ticket?: KitchenTicketOut;
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------
export const authApi = {
  login(email: string, password: string): Promise<TokenResponse> {
    return request<TokenResponse>("/v1/auth/login", {
      method: "POST",
      skipRefresh: true,
      body: { email, password },
    });
  },

  register(payload: RegisterPayload): Promise<TokenResponse> {
    return request<TokenResponse>("/v1/auth/register", {
      method: "POST",
      skipRefresh: true,
      body: payload,
    });
  },

  me(): Promise<UserOut> {
    return request<UserOut>("/v1/auth/me");
  },

  /** Explicitly restore a session from the httpOnly refresh cookie. */
  refresh(): Promise<boolean> {
    return request<{ access_token: string }>("/v1/auth/refresh", {
      method: "POST",
      skipRefresh: true,
    })
      .then((data) => {
        setAccessToken(data.access_token);
        return true;
      })
      .catch(() => false);
  },

  logout(): Promise<void> {
    return request<void>("/v1/auth/logout", {
      method: "POST",
      skipRefresh: true,
    });
  },

  /** Fire-and-forget reset request; 202 for existing AND unknown addresses. */
  requestPasswordReset(email: string): Promise<void> {
    return request<void>("/v1/auth/password-reset/request", {
      method: "POST",
      skipRefresh: true,
      body: { email },
    });
  },

  confirmPasswordReset(token: string, newPassword: string): Promise<void> {
    return request<void>("/v1/auth/password-reset/confirm", {
      method: "POST",
      skipRefresh: true,
      body: { token, new_password: newPassword },
    });
  },
};

// ---------------------------------------------------------------------------
// Restaurant endpoints
// ---------------------------------------------------------------------------
export const restaurantsApi = {
  getMine(): Promise<RestaurantOut> {
    return request<RestaurantOut>("/v1/restaurant/me");
  },
};

// --- Staff -------------------------------------------------------------
export interface StaffOut {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
}

export type StaffRole = "MANAGER" | "CASHIER" | "WAITER" | "KITCHEN" | "ACCOUNTANT";

export interface StaffCreate {
  full_name: string;
  email: string;
  password: string;
  role: StaffRole;
}

export const usersApi = {
  list(): Promise<StaffOut[]> {
    return request<StaffOut[]>("/v1/users");
  },
  create(payload: StaffCreate): Promise<StaffOut> {
    return request<StaffOut>("/v1/users", { method: "POST", body: payload });
  },
};

// ---------------------------------------------------------------------------
// Branch endpoints
// ---------------------------------------------------------------------------
export const branchesApi = {
  list(): Promise<BranchOut[]> {
    return request<BranchOut[]>("/v1/branches");
  },
};

// ---------------------------------------------------------------------------
// Menu endpoints
// ---------------------------------------------------------------------------
export const menuApi = {
  listCategories(limit = 100, offset = 0): Promise<CategoryOut[]> {
    return request<CategoryOut[]>(
      `/v1/menu/categories?limit=${limit}&offset=${offset}`
    );
  },

  getCategoryTree(
    limit = 100,
    offset = 0
  ): Promise<PageResponse<CategoryOut>> {
    return request<PageResponse<CategoryOut>>(
      `/v1/menu/categories/tree?limit=${limit}&offset=${offset}`
    );
  },

  createCategory(payload: CategoryCreate): Promise<CategoryOut> {
    return request<CategoryOut>("/v1/menu/categories", {
      method: "POST",
      body: payload,
    });
  },

  updateCategory(id: string, payload: CategoryUpdate): Promise<CategoryOut> {
    return request<CategoryOut>(`/v1/menu/categories/${id}`, {
      method: "PATCH",
      body: payload,
    });
  },

  deleteCategory(id: string): Promise<void> {
    return request<void>(`/v1/menu/categories/${id}`, { method: "DELETE" });
  },

  listProducts(
    limit = 100,
    offset = 0,
    categoryId?: string
  ): Promise<PageResponse<ProductOut>> {
    let url = `/v1/menu/products?limit=${limit}&offset=${offset}`;
    if (categoryId) url += `&category_id=${categoryId}`;
    return request<PageResponse<ProductOut>>(url);
  },

  createProduct(payload: ProductCreate): Promise<ProductOut> {
    return request<ProductOut>("/v1/menu/products", {
      method: "POST",
      body: payload,
    });
  },

  updateProduct(id: string, payload: ProductUpdate): Promise<ProductOut> {
    return request<ProductOut>(`/v1/menu/products/${id}`, {
      method: "PATCH",
      body: payload,
    });
  },

  deleteProduct(id: string): Promise<void> {
    return request<void>(`/v1/menu/products/${id}`, { method: "DELETE" });
  },
};

// ---------------------------------------------------------------------------
// Table endpoints
// ---------------------------------------------------------------------------
export const tablesApi = {
  list(branchId?: string): Promise<TableOut[]> {
    let url = "/v1/tables";
    if (branchId) url += `?branch_id=${branchId}`;
    return request<TableOut[]>(url);
  },

  get(id: string): Promise<TableOut> {
    return request<TableOut>(`/v1/tables/${id}`);
  },

  create(payload: TableCreate): Promise<TableOut> {
    return request<TableOut>("/v1/tables", { method: "POST", body: payload });
  },

  update(id: string, payload: TableUpdate): Promise<TableOut> {
    return request<TableOut>(`/v1/tables/${id}`, {
      method: "PATCH",
      body: payload,
    });
  },
};

// ---------------------------------------------------------------------------
// Order endpoints
// ---------------------------------------------------------------------------
export const ordersApi = {
  list(params: {
    branch_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<PageResponse<OrderOut>> {
    const sp = new URLSearchParams();
    if (params.branch_id) sp.set("branch_id", params.branch_id);
    if (params.status) sp.set("status", params.status);
    sp.set("limit", String(params.limit ?? 20));
    sp.set("offset", String(params.offset ?? 0));
    return request<PageResponse<OrderOut>>(`/v1/orders?${sp.toString()}`);
  },

  get(id: string): Promise<OrderOut> {
    return request<OrderOut>(`/v1/orders/${id}`);
  },

  create(
    payload: OrderCreate,
    idempotencyKey?: string
  ): Promise<OrderOut> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return request<OrderOut>("/v1/orders", {
      method: "POST",
      body: payload,
      headers,
    });
  },

  updateStatus(id: string, status: string): Promise<OrderOut> {
    return request<OrderOut>(`/v1/orders/${id}/status`, {
      method: "PATCH",
      body: { status },
    });
  },

  updateKitchenStatus(id: string, kitchenStatus: string): Promise<OrderOut> {
    return request<OrderOut>(`/v1/orders/${id}/kitchen-status`, {
      method: "PATCH",
      body: { kitchen_status: kitchenStatus },
    });
  },
};

// ---------------------------------------------------------------------------
// Kitchen endpoints
// ---------------------------------------------------------------------------
export const kitchenApi = {
  listTickets(branchId: string): Promise<KitchenTicketOut[]> {
    return request<KitchenTicketOut[]>(
      `/v1/kitchen/tickets?branch_id=${encodeURIComponent(branchId)}`
    );
  },

  updateTicketStatus(id: string, status: KitchenTicketStatus): Promise<KitchenTicketOut> {
    return request<KitchenTicketOut>(`/v1/kitchen/tickets/${id}/status`, {
      method: "PATCH",
      body: { status },
    });
  },

  listStations(branchId?: string): Promise<KitchenStationOut[]> {
    let url = "/v1/kitchen/stations";
    if (branchId) url += `?branch_id=${encodeURIComponent(branchId)}`;
    return request<KitchenStationOut[]>(url);
  },

  createStation(payload: KitchenStationCreate): Promise<KitchenStationOut> {
    return request<KitchenStationOut>("/v1/kitchen/stations", {
      method: "POST",
      body: payload,
    });
  },
};

// ---------------------------------------------------------------------------
// Payment endpoints
// ---------------------------------------------------------------------------
export const paymentsApi = {
  add(payload: PaymentCreate): Promise<PaymentOut> {
    return request<PaymentOut>("/v1/payments", {
      method: "POST",
      body: payload,
    });
  },

  listForOrder(orderId: string): Promise<PaymentOut[]> {
    return request<PaymentOut[]>(`/v1/orders/${orderId}/payments`);
  },

  /** Build a Payme check-out link for an open order (gateway opens in a tab). */
  paymeCheckout(orderId: string, amount: string): Promise<CheckoutResponse> {
    return request<CheckoutResponse>(`/v1/payments/${orderId}/payme-checkout`, {
      method: "POST",
      body: { amount },
    });
  },

  listCashShifts(branchId?: string): Promise<CashShiftOut[]> {
    let url = "/v1/cash-shifts";
    if (branchId) url += `?branch_id=${branchId}`;
    return request<CashShiftOut[]>(url);
  },

  openCashShift(
    branchId: string,
    openingBalance: string
  ): Promise<CashShiftOut> {
    return request<CashShiftOut>("/v1/cash-shifts/open", {
      method: "POST",
      body: { branch_id: branchId, opening_balance: openingBalance },
    });
  },

  closeCashShift(
    shiftId: string,
    actualClosingBalance: string,
    version: number
  ): Promise<CashShiftOut> {
    return request<CashShiftOut>(`/v1/cash-shifts/${shiftId}/close`, {
      method: "POST",
      body: { actual_closing_balance: actualClosingBalance, version },
    });
  },
};

// ---------------------------------------------------------------------------
// Upload endpoint (multipart/form-data — bypasses the JSON `request` helper,
// but shares its auth token + silent-refresh-on-401 behavior).
// ---------------------------------------------------------------------------
export interface UploadResponse {
  url: string;
  filename: string;
}

export const uploadsApi = {
  async uploadImage(file: File): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);

    const send = (token: string | null) =>
      fetch(`${API_BASE}/v1/uploads/image`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: form,
      });

    let res = await send(accessToken);
    if (res.status === 401) {
      const refreshed = await refreshSession();
      res = refreshed ? await send(accessToken) : res;
    }
    if (!res.ok) {
      throw new ApiError(res.status, await parseError(res));
    }
    return (await res.json()) as UploadResponse;
  },
};
