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
  /** Machine-readable reason for 402s: "plan_upgrade_required" | "subscription_expired". */
  readonly code?: string;
  /** Extra context sent with a coded error (e.g. `required_plan`). */
  readonly data?: Record<string, unknown>;

  constructor(status: number, detail: string, code?: string, data?: Record<string, unknown>) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
    this.data = data;
  }
}

/** Fired on every 402 so the dashboard can refresh the subscription state and
 * explain what happened, whichever page triggered it. */
export const PAYMENT_REQUIRED_EVENT = "synora:payment-required";

/** Thrown when `fetch()` itself fails (no connectivity) — distinct from
 * ApiError, which means the server was reached and responded with an error.
 * Callers (e.g. the offline queue) use this to decide "queue it" vs "show
 * the error". */
export class OfflineError extends Error {
  constructor() {
    super("Network request failed — you appear to be offline.");
    this.name = "OfflineError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  /** Endpoints that must never trigger the silent-refresh loop. */
  skipRefresh?: boolean;
}

interface ParsedError {
  message: string;
  code?: string;
  data?: Record<string, unknown>;
}

async function parseErrorFull(res: Response): Promise<ParsedError> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return { message: data.detail };
    if (data.detail && typeof data.detail === "object" && !Array.isArray(data.detail)) {
      const { code, message, ...rest } = data.detail as Record<string, unknown>;
      return {
        message: typeof message === "string" ? message : res.statusText || `Request failed (${res.status}).`,
        code: typeof code === "string" ? code : undefined,
        data: rest,
      };
    }
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0] as { msg?: string };
      if (first && typeof first.msg === "string") return { message: first.msg };
    }
  } catch {
    // Not JSON; fall through to status text.
  }
  return { message: res.statusText || `Request failed (${res.status}).` };
}

async function parseError(res: Response): Promise<string> {
  return (await parseErrorFull(res)).message;
}

async function toApiError(res: Response): Promise<ApiError> {
  const parsed = await parseErrorFull(res);
  if (res.status === 402 && typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(PAYMENT_REQUIRED_EVENT, { detail: { code: parsed.code, data: parsed.data } }));
  }
  return new ApiError(res.status, parsed.message, parsed.code, parsed.data);
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
    .catch(() => false)
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
    try {
      return await fetch(finalPath, init);
    } catch {
      throw new OfflineError();
    }
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
    throw await toApiError(res);
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
  username: string;
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
  username: string;
  full_name: string;
  restaurant_id: string;
  restaurant_name: string;
  roles: RoleOut[];
  permissions: string[];
  is_platform_admin?: boolean;
}

// --- Waiter kiosk PIN login -------------------------------------------------
export interface WaiterBranchOut {
  id: string;
  name: string;
  restaurant_name: string;
}

export interface WaiterDirectoryEntry {
  id: string;
  full_name: string;
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
  telegram_bot_username: string | null;
  telegram_connected: boolean;
  payment_card_number: string | null;
  payment_card_holder: string | null;
}

export interface TelegramStatusOut {
  telegram_connected: boolean;
  telegram_bot_username: string | null;
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

export interface BranchCreate {
  name: string;
  address?: string | null;
  phone?: string | null;
  timezone?: string | null;
  currency?: string | null;
}

export interface BranchUpdate {
  name?: string;
  address?: string | null;
  phone?: string | null;
  timezone?: string | null;
  currency?: string | null;
  is_active?: boolean;
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
  /** Optional hall/room grouping ("1-zal", "Terassa"); null = ungrouped. */
  zone: string | null;
  capacity: number;
  status: string;
  is_active: boolean;
  version: number;
}

export interface TableCreate {
  branch_id: string;
  name: string;
  zone?: string | null;
  capacity?: number;
}

export interface TableUpdate {
  name?: string;
  zone?: string | null;
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
  /** Currency amount when discount_type="FIXED", 0-100 when "PERCENT". */
  discount_type?: "FIXED" | "PERCENT";
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
  discount_type: string;
  discount: string;
  tax: string;
  service_charge: string;
  total: string;
  currency: string;
  notes: string | null;
  waiter_user_id: string | null;
  waiter_name: string | null;
  created_by_user_id: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  bill_requested_at: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  delivery_type: "DELIVERY" | "PICKUP" | null;
  delivery_address: string | null;
  delivery_lat: string | null;
  delivery_lng: string | null;
  delivery_note: string | null;
  payment_method: "CASH" | "CARD_TRANSFER" | "PAYME" | null;
  payment_proof_url: string | null;
  items: OrderItemOut[];
  created_at: string;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- Split bill --------------------------------------------------------------
export interface SplitItemGroup {
  label: string;
  order_item_ids: string[];
}

export interface SplitPreviewRequest {
  mode: "person" | "item" | "amount";
  parts?: number;
  item_groups?: SplitItemGroup[];
  amounts?: string[];
}

export interface SplitShare {
  label: string;
  amount: string;
}

export interface SplitPreviewOut {
  mode: string;
  order_total: string;
  shares: SplitShare[];
}

// --- Waiter stats --------------------------------------------------------------
export interface WaiterStatsOut {
  waiter_user_id: string;
  date_from: string;
  date_to: string;
  total_sales: string;
  order_count: number;
  tables_served: number;
  average_check: string;
  cancelled_count: number;
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
  login(username: string, password: string): Promise<TokenResponse> {
    return request<TokenResponse>("/v1/auth/login", {
      method: "POST",
      skipRefresh: true,
      body: { username, password },
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

  waiterBranches(): Promise<WaiterBranchOut[]> {
    return request<WaiterBranchOut[]>("/v1/auth/waiter-branches", {
      skipRefresh: true,
    });
  },

  waiterDirectory(branchId: string): Promise<WaiterDirectoryEntry[]> {
    return request<WaiterDirectoryEntry[]>(
      `/v1/auth/waiter-directory?branch_id=${branchId}`,
      { skipRefresh: true }
    );
  },

  pinLogin(branchId: string, userId: string, pin: string): Promise<TokenResponse> {
    return request<TokenResponse>("/v1/auth/pin-login", {
      method: "POST",
      skipRefresh: true,
      body: { branch_id: branchId, user_id: userId, pin },
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
  connectTelegram(botToken: string): Promise<TelegramStatusOut> {
    return request<TelegramStatusOut>("/v1/restaurant/telegram", {
      method: "POST",
      body: { bot_token: botToken },
    });
  },
  updatePaymentDetails(payload: {
    payment_card_number: string | null;
    payment_card_holder: string | null;
  }): Promise<RestaurantOut> {
    return request<RestaurantOut>("/v1/restaurant/me", { method: "PATCH", body: payload });
  },
  disconnectTelegram(): Promise<TelegramStatusOut> {
    return request<TelegramStatusOut>("/v1/restaurant/telegram", { method: "DELETE" });
  },
};

// --- Staff -------------------------------------------------------------
export interface StaffOut {
  id: string;
  username: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
  has_pin: boolean;
}

export type StaffRole = "MANAGER" | "CASHIER" | "WAITER" | "KITCHEN" | "ACCOUNTANT";

export interface StaffCreate {
  full_name: string;
  username: string;
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
  /** Set (or, with an empty string, clear) a staff member's waiter-kiosk PIN. */
  setPin(id: string, pin: string): Promise<StaffOut> {
    return request<StaffOut>(`/v1/users/${id}/pin`, {
      method: "PATCH",
      body: { pin },
    });
  },
  /** Admin resets a staff member's login password — no self-service reset exists. */
  setPassword(id: string, password: string): Promise<StaffOut> {
    return request<StaffOut>(`/v1/users/${id}/password`, {
      method: "PATCH",
      body: { password },
    });
  },
  update(id: string, payload: { full_name?: string; phone?: string }): Promise<StaffOut> {
    return request<StaffOut>(`/v1/users/${id}`, { method: "PATCH", body: payload });
  },
  changeRole(id: string, role: StaffRole): Promise<StaffOut> {
    return request<StaffOut>(`/v1/users/${id}/role`, { method: "PATCH", body: { role } });
  },
  setActive(id: string, isActive: boolean): Promise<StaffOut> {
    return request<StaffOut>(`/v1/users/${id}/active`, {
      method: "PATCH",
      body: { is_active: isActive },
    });
  },
};

// ---------------------------------------------------------------------------
// Branch endpoints
// ---------------------------------------------------------------------------
export const branchesApi = {
  list(): Promise<BranchOut[]> {
    return request<BranchOut[]>("/v1/branches");
  },
  get(id: string): Promise<BranchOut> {
    return request<BranchOut>(`/v1/branches/${id}`);
  },
  create(payload: BranchCreate): Promise<BranchOut> {
    return request<BranchOut>("/v1/branches", { method: "POST", body: payload });
  },
  update(id: string, payload: BranchUpdate): Promise<BranchOut> {
    return request<BranchOut>(`/v1/branches/${id}`, { method: "PATCH", body: payload });
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
    waiter_user_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<PageResponse<OrderOut>> {
    const sp = new URLSearchParams();
    if (params.branch_id) sp.set("branch_id", params.branch_id);
    if (params.status) sp.set("status", params.status);
    if (params.waiter_user_id) sp.set("waiter_user_id", params.waiter_user_id);
    sp.set("limit", String(params.limit ?? 20));
    sp.set("offset", String(params.offset ?? 0));
    return request<PageResponse<OrderOut>>(`/v1/orders?${sp.toString()}`);
  },

  get(id: string): Promise<OrderOut> {
    return request<OrderOut>(`/v1/orders/${id}`);
  },

  /** DRAFT + OPEN + PARTIALLY_PAID orders for a branch — the live floor. */
  listActive(branchId?: string): Promise<OrderOut[]> {
    const qs = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
    return request<OrderOut[]>(`/v1/orders/active${qs}`);
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

  applyDiscount(
    id: string,
    discountType: "FIXED" | "PERCENT",
    discount: string
  ): Promise<OrderOut> {
    return request<OrderOut>(`/v1/orders/${id}/discount`, {
      method: "PATCH",
      body: { discount_type: discountType, discount },
    });
  },

  requestBill(id: string): Promise<OrderOut> {
    return request<OrderOut>(`/v1/orders/${id}/request-bill`, { method: "POST" });
  },

  print(id: string, kind: "PRECHECK" | "RECEIPT"): Promise<PrintJobOut> {
    return request<PrintJobOut>(`/v1/orders/${id}/print?kind=${kind}`, { method: "POST" });
  },

  reprintKitchen(id: string): Promise<PrintJobOut> {
    return request<PrintJobOut>(`/v1/orders/${id}/reprint-kitchen`, { method: "POST" });
  },

  transferTable(id: string, tableId: string): Promise<OrderOut> {
    return request<OrderOut>(`/v1/orders/${id}/table`, {
      method: "PATCH",
      body: { table_id: tableId },
    });
  },

  mergeInto(sourceOrderId: string, targetOrderId: string): Promise<OrderOut> {
    return request<OrderOut>(
      `/v1/orders/${sourceOrderId}/merge-into/${targetOrderId}`,
      { method: "POST" }
    );
  },

  previewSplit(id: string, payload: SplitPreviewRequest): Promise<SplitPreviewOut> {
    return request<SplitPreviewOut>(`/v1/orders/${id}/split-preview`, {
      method: "POST",
      body: payload,
    });
  },

  myStats(dateFrom?: string, dateTo?: string): Promise<WaiterStatsOut> {
    const sp = new URLSearchParams();
    if (dateFrom) sp.set("date_from", dateFrom);
    if (dateTo) sp.set("date_to", dateTo);
    const qs = sp.toString();
    return request<WaiterStatsOut>(`/v1/orders/stats/me${qs ? `?${qs}` : ""}`);
  },

  statsFor(waiterUserId: string, dateFrom?: string, dateTo?: string): Promise<WaiterStatsOut> {
    const sp = new URLSearchParams();
    if (dateFrom) sp.set("date_from", dateFrom);
    if (dateTo) sp.set("date_to", dateTo);
    const qs = sp.toString();
    return request<WaiterStatsOut>(`/v1/orders/stats/${waiterUserId}${qs ? `?${qs}` : ""}`);
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

// ---------------------------------------------------------------------------
// Inventory endpoints
// ---------------------------------------------------------------------------
export interface InventoryItemOut {
  id: string;
  branch_id: string;
  name: string;
  unit: string;
  quantity: string;
  minimum_quantity: string;
  cost_per_unit: string;
  supplier: string | null;
  is_active: boolean;
  is_low_stock: boolean;
}

export interface InventoryItemCreate {
  branch_id: string;
  name: string;
  unit: string;
  minimum_quantity?: string;
  cost_per_unit?: string;
  supplier?: string | null;
}

export interface InventoryItemUpdate {
  name?: string;
  unit?: string;
  minimum_quantity?: string;
  cost_per_unit?: string;
  supplier?: string | null;
  is_active?: boolean;
}

export type InventoryTransactionType = "IN" | "OUT" | "ADJUSTMENT";

export interface InventoryTransactionOut {
  id: string;
  inventory_item_id: string;
  type: InventoryTransactionType;
  quantity: string;
  reason: string | null;
  created_by_user_id: string | null;
  created_at: string;
}

export const inventoryApi = {
  list(branchId?: string): Promise<InventoryItemOut[]> {
    const qs = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
    return request<InventoryItemOut[]>(`/v1/inventory-items${qs}`);
  },
  create(payload: InventoryItemCreate): Promise<InventoryItemOut> {
    return request<InventoryItemOut>("/v1/inventory-items", { method: "POST", body: payload });
  },
  update(id: string, payload: InventoryItemUpdate): Promise<InventoryItemOut> {
    return request<InventoryItemOut>(`/v1/inventory-items/${id}`, { method: "PATCH", body: payload });
  },
  addTransaction(
    id: string,
    type: InventoryTransactionType,
    quantity: string,
    reason?: string
  ): Promise<InventoryItemOut> {
    return request<InventoryItemOut>(`/v1/inventory-items/${id}/transactions`, {
      method: "POST",
      body: { type, quantity, reason },
    });
  },
  listTransactions(id: string): Promise<InventoryTransactionOut[]> {
    return request<InventoryTransactionOut[]>(`/v1/inventory-items/${id}/transactions`);
  },
};

// ---------------------------------------------------------------------------
// Expense endpoints
// ---------------------------------------------------------------------------
export type ExpenseCategory = "RENT" | "SALARY" | "PRODUCT" | "UTILITIES" | "OTHER";

export interface ExpenseOut {
  id: string;
  branch_id: string;
  category: ExpenseCategory;
  amount: string;
  description: string | null;
  expense_date: string;
  created_by_user_id: string | null;
  created_at: string;
}

export interface ExpenseCreate {
  branch_id: string;
  category: ExpenseCategory;
  amount: string;
  description?: string | null;
  expense_date: string;
}

export interface ExpenseUpdate {
  category?: ExpenseCategory;
  amount?: string;
  description?: string | null;
  expense_date?: string;
}

export const expensesApi = {
  list(params: {
    branch_id?: string;
    category?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<ExpenseOut[]> {
    const sp = new URLSearchParams();
    if (params.branch_id) sp.set("branch_id", params.branch_id);
    if (params.category) sp.set("category", params.category);
    if (params.date_from) sp.set("date_from", params.date_from);
    if (params.date_to) sp.set("date_to", params.date_to);
    const qs = sp.toString();
    return request<ExpenseOut[]>(`/v1/expenses${qs ? `?${qs}` : ""}`);
  },
  create(payload: ExpenseCreate): Promise<ExpenseOut> {
    return request<ExpenseOut>("/v1/expenses", { method: "POST", body: payload });
  },
  update(id: string, payload: ExpenseUpdate): Promise<ExpenseOut> {
    return request<ExpenseOut>(`/v1/expenses/${id}`, { method: "PATCH", body: payload });
  },
  delete(id: string): Promise<void> {
    return request<void>(`/v1/expenses/${id}`, { method: "DELETE" });
  },
};

// ---------------------------------------------------------------------------
// Reports endpoints
// ---------------------------------------------------------------------------
export interface SalesPoint {
  bucket: string;
  revenue: string;
  order_count: number;
}

export interface SalesSeriesOut {
  group_by: "day" | "week" | "month";
  points: SalesPoint[];
}

export interface ProductReportRow {
  product_name: string;
  quantity: number;
  revenue: string;
}

export interface WaiterReportRow {
  waiter_user_id: string;
  waiter_name: string;
  total_sales: string;
  order_count: number;
  average_check: string;
}

export interface PaymentReportRow {
  method: string;
  amount: string;
  count: number;
}

export interface ExpenseReportRow {
  category: string;
  amount: string;
}

export interface ProfitReportOut {
  revenue: string;
  expenses: string;
  profit: string;
}

export interface ReportRangeParams {
  branch_id?: string;
  date_from?: string;
  date_to?: string;
}

function reportQuery(params: object): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "string" && value) sp.set(key, value);
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export const reportsApi = {
  sales(params: ReportRangeParams & { group_by?: "day" | "week" | "month" }): Promise<SalesSeriesOut> {
    return request<SalesSeriesOut>(`/v1/reports/sales${reportQuery(params)}`);
  },
  products(params: ReportRangeParams): Promise<ProductReportRow[]> {
    return request<ProductReportRow[]>(`/v1/reports/products${reportQuery(params)}`);
  },
  waiters(params: ReportRangeParams): Promise<WaiterReportRow[]> {
    return request<WaiterReportRow[]>(`/v1/reports/waiters${reportQuery(params)}`);
  },
  payments(params: ReportRangeParams): Promise<PaymentReportRow[]> {
    return request<PaymentReportRow[]>(`/v1/reports/payments${reportQuery(params)}`);
  },
  expenses(params: ReportRangeParams): Promise<ExpenseReportRow[]> {
    return request<ExpenseReportRow[]>(`/v1/reports/expenses${reportQuery(params)}`);
  },
  profit(params: ReportRangeParams): Promise<ProfitReportOut> {
    return request<ProfitReportOut>(`/v1/reports/profit${reportQuery(params)}`);
  },
};

// ---------------------------------------------------------------------------
// Customer / CRM endpoints
// ---------------------------------------------------------------------------
export interface CustomerOut {
  id: string;
  full_name: string | null;
  phone: string | null;
  telegram_user_id: number | null;
  created_at: string;
}

export interface CustomerOrderSummary {
  id: string;
  order_number: number;
  total: string;
  status: string;
  created_at: string;
}

export interface CustomerDetailOut {
  customer: CustomerOut;
  total_orders: number;
  total_spent: string;
  last_visit: string | null;
  favorite_products: string[];
  recent_orders: CustomerOrderSummary[];
}

export const customersApi = {
  list(search?: string): Promise<CustomerOut[]> {
    const qs = search ? `?search=${encodeURIComponent(search)}` : "";
    return request<CustomerOut[]>(`/v1/customers${qs}`);
  },
  get(id: string): Promise<CustomerDetailOut> {
    return request<CustomerDetailOut>(`/v1/customers/${id}`);
  },
};

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------
export interface NotificationOut {
  id: string;
  branch_id: string | null;
  type: "NEW_ORDER" | "LOW_STOCK" | "PAYMENT" | "ORDER_CANCELLED" | "BILL_REQUEST" | "SUBSCRIPTION";
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export const notificationsApi = {
  list(limit = 30, offset = 0): Promise<NotificationOut[]> {
    return request<NotificationOut[]>(`/v1/notifications?limit=${limit}&offset=${offset}`);
  },
  markRead(id: string): Promise<NotificationOut> {
    return request<NotificationOut>(`/v1/notifications/${id}/read`, { method: "PATCH" });
  },
  markAllRead(): Promise<void> {
    return request<void>("/v1/notifications/mark-all-read", { method: "POST" });
  },
};

export interface NotificationEvent {
  event: "notification";
  notification: NotificationOut;
}

// ---------------------------------------------------------------------------
// Audit log
// ---------------------------------------------------------------------------
export interface AuditLogOut {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  created_at: string;
}

export const auditApi = {
  list(params?: { action?: string; limit?: number; offset?: number }): Promise<AuditLogOut[]> {
    const sp = new URLSearchParams();
    if (params?.action) sp.set("action", params.action);
    sp.set("limit", String(params?.limit ?? 50));
    sp.set("offset", String(params?.offset ?? 0));
    return request<AuditLogOut[]>(`/v1/audit-log?${sp.toString()}`);
  },
};

// ---------------------------------------------------------------------------
// Receipt printers (network ESC/POS)
// ---------------------------------------------------------------------------
export type PrinterRole = "KITCHEN" | "RECEIPT";

export interface PrinterOut {
  id: string;
  branch_id: string;
  name: string;
  role: PrinterRole;
  host: string;
  port: number;
  paper_width: 58 | 80;
  is_active: boolean;
  auto_print_receipt: boolean;
  auto_print_orders: boolean;
  mode: PrinterMode;
}

export type PrinterMode = "DIRECT" | "AGENT";

export interface AgentStatus {
  configured: boolean;
  last_seen_at: string | null;
  online: boolean;
}

export interface PrinterCreate {
  branch_id: string;
  role: PrinterRole;
  name: string;
  host: string;
  port: number;
  paper_width: 58 | 80;
  is_active: boolean;
  auto_print_receipt: boolean;
  auto_print_orders: boolean;
  mode: PrinterMode;
}

export type PrinterUpdate = Partial<Omit<PrinterCreate, "branch_id" | "role">>;

export interface PrintJobOut {
  id: string;
  branch_id: string;
  printer_id: string | null;
  kind: "KITCHEN_TICKET" | "ORDER_COPY" | "PRECHECK" | "RECEIPT" | "TEST";
  order_id: string | null;
  status: "PENDING" | "PRINTED" | "FAILED";
  attempts: number;
  error: string | null;
  created_at: string;
  printed_at: string | null;
}

export const printersApi = {
  list(branchId?: string): Promise<PrinterOut[]> {
    const qs = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
    return request<PrinterOut[]>(`/v1/printers${qs}`);
  },
  capabilities(branchId: string): Promise<{ kitchen: boolean; receipt: boolean }> {
    return request(`/v1/printers/capabilities?branch_id=${encodeURIComponent(branchId)}`);
  },
  create(payload: PrinterCreate): Promise<PrinterOut> {
    return request<PrinterOut>("/v1/printers", { method: "POST", body: payload });
  },
  update(id: string, payload: PrinterUpdate): Promise<PrinterOut> {
    return request<PrinterOut>(`/v1/printers/${id}`, { method: "PATCH", body: payload });
  },
  remove(id: string): Promise<void> {
    return request<void>(`/v1/printers/${id}`, { method: "DELETE" });
  },
  test(id: string): Promise<PrintJobOut> {
    return request<PrintJobOut>(`/v1/printers/${id}/test`, { method: "POST" });
  },
  agentStatus(branchId: string): Promise<AgentStatus> {
    return request<AgentStatus>(`/v1/printers/agent?branch_id=${encodeURIComponent(branchId)}`);
  },
  rotateAgentToken(branchId: string): Promise<{ token: string }> {
    return request<{ token: string }>(`/v1/printers/agent/token?branch_id=${encodeURIComponent(branchId)}`, {
      method: "POST",
    });
  },
};

export const printJobsApi = {
  list(limit = 30): Promise<PrintJobOut[]> {
    return request<PrintJobOut[]>(`/v1/print-jobs?limit=${limit}`);
  },
  retry(id: string): Promise<PrintJobOut> {
    return request<PrintJobOut>(`/v1/print-jobs/${id}/retry`, { method: "POST" });
  },
};

// ---------------------------------------------------------------------------
// Global search
// ---------------------------------------------------------------------------
export interface SearchOrderHit {
  id: string;
  order_number: number;
  status: string;
  total: string;
}

export interface SearchProductHit {
  id: string;
  name: string;
  price: string;
}

export interface SearchCustomerHit {
  id: string;
  full_name: string | null;
  phone: string | null;
}

export interface SearchStaffHit {
  id: string;
  full_name: string;
  username: string;
}

export interface SearchTableHit {
  id: string;
  name: string;
  zone: string | null;
}

export interface SearchResultsOut {
  orders: SearchOrderHit[];
  products: SearchProductHit[];
  customers: SearchCustomerHit[];
  staff: SearchStaffHit[];
  tables: SearchTableHit[];
}

export const searchApi = {
  search(q: string): Promise<SearchResultsOut> {
    return request<SearchResultsOut>(`/v1/search?q=${encodeURIComponent(q)}`);
  },
};

// ---------------------------------------------------------------------------
// Public (unauthenticated) QR-menu endpoints
// ---------------------------------------------------------------------------
export interface PublicModifierOut {
  id: string;
  name: string;
  price: string;
  sort_order: number;
  is_active: boolean;
}

export interface PublicModifierGroupOut {
  id: string;
  name: string;
  is_required: boolean;
  min_selections: number;
  max_selections: number;
  is_active: boolean;
  modifiers: PublicModifierOut[];
}

export interface PublicProductOut {
  id: string;
  name: string;
  description: string | null;
  price: string;
  image_url: string | null;
  modifier_groups: PublicModifierGroupOut[];
}

export interface PublicCategoryOut {
  id: string;
  name: string;
  description: string | null;
  image_url: string | null;
  products: PublicProductOut[];
}

export interface PublicBranchOut {
  id: string;
  name: string;
  address: string | null;
}

export interface PublicMenuOut {
  restaurant_name: string;
  currency: string;
  branches: PublicBranchOut[];
  categories: PublicCategoryOut[];
}

export interface PublicTableOut {
  id: string;
  name: string;
  capacity: number;
}

export interface PublicOrderItemIn {
  product_id: string;
  quantity?: number;
  notes?: string;
  modifiers?: OrderModifierSelection[];
}

export interface PublicOrderCreate {
  restaurant_slug: string;
  branch_id: string;
  table_id: string;
  customer_name: string;
  customer_phone?: string;
  notes?: string;
  items: PublicOrderItemIn[];
}

export interface PublicOrderOut {
  order_number: number;
  total: string;
  currency: string;
}

export const publicApi = {
  menu(restaurantSlug: string): Promise<PublicMenuOut> {
    return request<PublicMenuOut>(`/v1/public/menu/${encodeURIComponent(restaurantSlug)}`);
  },
  tables(restaurantSlug: string, branchId: string): Promise<PublicTableOut[]> {
    return request<PublicTableOut[]>(
      `/v1/public/tables/${encodeURIComponent(restaurantSlug)}/${branchId}`
    );
  },
  createOrder(payload: PublicOrderCreate, idempotencyKey?: string): Promise<PublicOrderOut> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return request<PublicOrderOut>("/v1/public/orders", { method: "POST", body: payload, headers });
  },
};

// --- Subscription (plans, limits, card-transfer payments) ---------------------
export type PlanName = "BUSINESS" | "PRO" | "AI_PREMIUM" | "ENTERPRISE";
export type BillingCycle = "MONTHLY" | "ANNUAL";
export type AccessLevel = "FULL" | "GRACE" | "READ_ONLY";

export interface SubscriptionOut {
  plan: PlanName;
  status: "TRIAL" | "ACTIVE";
  access: AccessLevel;
  can_write: boolean;
  ends_at: string | null;
  days_left: number | null;
  grace_days_left: number | null;
  billing_cycle: BillingCycle | null;
  branch_count: number;
  branch_limit: number | null;
  features: string[];
}

export interface PlanInfo {
  plan: PlanName;
  monthly_price: number | null;
  annual_price: number | null;
  branch_limit: number | null;
  features: string[];
}

export interface PlansOut {
  plans: PlanInfo[];
  currency: string;
  payment_card: string;
  payment_holder: string;
  trial_days: number;
  grace_days: number;
}

export interface SubscriptionPaymentOut {
  id: string;
  restaurant_id: string;
  plan: PlanName;
  billing_cycle: BillingCycle;
  amount: string;
  currency: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  receipt_url: string | null;
  note: string | null;
  reviewed_at: string | null;
  period_start: string | null;
  period_end: string | null;
  created_at: string;
}

export interface PlatformPaymentOut extends SubscriptionPaymentOut {
  restaurant_name: string;
}

export interface PlatformRestaurantOut {
  id: string;
  name: string;
  slug: string;
  plan: PlanName;
  effective_plan: PlanName;
  status: "TRIAL" | "ACTIVE";
  access: AccessLevel;
  ends_at: string | null;
  days_left: number | null;
  created_at: string;
}

export const subscriptionApi = {
  get: () => request<SubscriptionOut>("/v1/subscription"),
  plans: () => request<PlansOut>("/v1/subscription/plans"),
  payments: () => request<SubscriptionPaymentOut[]>("/v1/subscription/payments"),
  requestPayment: (plan: PlanName, billing_cycle: BillingCycle) =>
    request<SubscriptionPaymentOut>("/v1/subscription/payments", { method: "POST", body: { plan, billing_cycle } }),
  attachReceipt: (id: string, receipt_url: string) =>
    request<SubscriptionPaymentOut>(`/v1/subscription/payments/${id}/receipt`, { method: "POST", body: { receipt_url } }),
};

export const platformApi = {
  restaurants: () => request<PlatformRestaurantOut[]>("/v1/platform/restaurants"),
  payments: (status?: SubscriptionPaymentOut["status"]) =>
    request<PlatformPaymentOut[]>(`/v1/platform/payments${status ? `?status=${status}` : ""}`),
  approve: (id: string) => request<PlatformPaymentOut>(`/v1/platform/payments/${id}/approve`, { method: "POST" }),
  reject: (id: string, reason?: string) =>
    request<PlatformPaymentOut>(`/v1/platform/payments/${id}/reject`, { method: "POST", body: { reason: reason || null } }),
  override: (
    id: string,
    body: { plan?: PlanName; status?: "TRIAL" | "ACTIVE"; period_end?: string; clear_period_end?: boolean }
  ) => request<PlatformRestaurantOut>(`/v1/platform/restaurants/${id}/subscription`, { method: "PATCH", body }),
};
