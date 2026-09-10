"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Pencil, Trash2 } from "lucide-react";
import {
  CategoryOut,
  ProductOut,
  menuApi,
  restaurantsApi,
} from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { formatMoney } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";

type ModalState =
  | { type: "createCategory" }
  | { type: "editCategory"; category: CategoryOut }
  | { type: "createProduct" }
  | { type: "editProduct"; product: ProductOut }
  | null;

type ConfirmState =
  | { type: "category"; target: CategoryOut }
  | { type: "product"; target: ProductOut }
  | null;

export default function MenuPage() {
  const t = useTranslations("menuPage");
  const tc = useTranslations("common");
  const { can } = useAuth();
  const [categories, setCategories] = useState<LoadState<CategoryOut[]>>(
    loadingState()
  );
  const [products, setProducts] = useState<LoadState<ProductOut[]>>(
    loadingState()
  );
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null
  );
  const [currency, setCurrency] = useState<string>("UZS");
  const [modal, setModal] = useState<ModalState>(null);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canCreate = can("menu.create");
  const canUpdate = can("menu.update");
  const canDelete = can("menu.delete");

  const loadCategories = useCallback(async () => {
    try {
      const list = await menuApi.listCategories(100, 0);
      setCategories(dataState(list));
      setSelectedCategoryId((prev) => prev ?? list[0]?.id ?? null);
    } catch (err) {
      setCategories(errorState((err as Error).message));
    }
  }, []);

  const loadProducts = useCallback(
    async (categoryId: string | null) => {
      try {
        const page = await menuApi.listProducts(100, 0, categoryId ?? undefined);
        setProducts(dataState(page.items));
      } catch (err) {
        setProducts(errorState((err as Error).message));
      }
    },
    []
  );

  useEffect(() => {
    void (async () => {
      try {
        const list = await menuApi.listCategories(100, 0);
        setCategories(dataState(list));
        setSelectedCategoryId((prev) => prev ?? list[0]?.id ?? null);
      } catch (err) {
        setCategories(errorState((err as Error).message));
      }
    })();
    restaurantsApi.getMine().then((r) => setCurrency(r.currency)).catch(() => {});
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const page = await menuApi.listProducts(100, 0, selectedCategoryId ?? undefined);
        setProducts(dataState(page.items));
      } catch (err) {
        setProducts(errorState((err as Error).message));
      }
    })();
  }, [selectedCategoryId]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const handleCreateCategory = async (name: string, description: string, sortOrder: number) => {
    try {
      await menuApi.createCategory({ name, description: description || null, sort_order: sortOrder });
      setModal(null);
      flash(tc("actions.saved"));
      loadCategories();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleUpdateCategory = async (
    category: CategoryOut,
    name: string,
    description: string,
    sortOrder: number
  ) => {
    try {
      await menuApi.updateCategory(category.id, {
        name,
        description: description || null,
        sort_order: sortOrder,
      });
      setModal(null);
      flash(tc("actions.saved"));
      loadCategories();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleDeleteCategory = async (category: CategoryOut) => {
    try {
      await menuApi.deleteCategory(category.id);
      setConfirm(null);
      flash(tc("actions.saved"));
      setSelectedCategoryId(null);
      loadCategories();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleCreateProduct = async (payload: {
    name: string;
    description: string;
    price: string;
    costPrice: string;
    categoryId: string | null;
    available: boolean;
  }) => {
    try {
      await menuApi.createProduct({
        name: payload.name,
        description: payload.description || null,
        price: payload.price,
        cost_price: payload.costPrice || "0.00",
        category_id: payload.categoryId,
        is_available: payload.available,
      });
      setModal(null);
      flash(tc("actions.saved"));
      loadProducts(payload.categoryId ?? null);
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleUpdateProduct = async (
    product: ProductOut,
    payload: {
      name: string;
      description: string;
      price: string;
      costPrice: string;
      categoryId: string | null;
      available: boolean;
    }
  ) => {
    try {
      await menuApi.updateProduct(product.id, {
        name: payload.name,
        description: payload.description || null,
        price: payload.price,
        cost_price: payload.costPrice || "0.00",
        category_id: payload.categoryId,
        is_available: payload.available,
      });
      setModal(null);
      flash(tc("actions.saved"));
      loadProducts(selectedCategoryId);
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleDeleteProduct = async (product: ProductOut) => {
    try {
      await menuApi.deleteProduct(product.id);
      setConfirm(null);
      flash(tc("actions.saved"));
      loadProducts(selectedCategoryId);
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleToggleAvailable = async (product: ProductOut) => {
    try {
      await menuApi.updateProduct(product.id, {
        is_available: !product.is_available,
      });
      loadProducts(selectedCategoryId);
    } catch (err) {
      alert((err as Error).message);
    }
  };

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          canCreate ? (
            <Button size="sm" onClick={() => setModal({ type: "createProduct" })}>
              <Plus className="h-4 w-4" />
              {t("addProduct")}
            </Button>
          ) : undefined
        }
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* Categories sidebar */}
        <aside className="rounded-xl border border-border-default bg-surface p-3">
          <div className="mb-2 flex items-center justify-between px-2">
            <h2 className="text-sm font-semibold text-text-primary">
              {t("categories")}
            </h2>
            {canCreate && (
              <button
                onClick={() => setModal({ type: "createCategory" })}
                aria-label={t("addCategory")}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-background-secondary hover:text-accent-primary"
              >
                <Plus className="h-4 w-4" />
              </button>
            )}
          </div>

          {categories.type === "data" ? (
            <nav className="flex flex-col gap-1">
              <button
                onClick={() => {
                  setProducts(loadingState());
                  setSelectedCategoryId(null);
                }}
                className={`rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors ${
                  selectedCategoryId === null
                    ? "bg-accent-primary/10 text-accent-primary"
                    : "text-text-secondary hover:bg-background-secondary hover:text-text-primary"
                }`}
              >
                {t("allCategories")}
              </button>
              {categories.data.map((category) => (
                <div
                  key={category.id}
                  className={`group flex items-center rounded-lg transition-colors ${
                    selectedCategoryId === category.id
                      ? "bg-accent-primary/10"
                      : "hover:bg-background-secondary"
                  }`}
                >
                  <button
                    onClick={() => {
                      setProducts(loadingState());
                      setSelectedCategoryId(category.id);
                    }}
                    className={`flex-1 truncate rounded-l-lg px-3 py-2 text-left text-sm font-medium ${
                      selectedCategoryId === category.id
                        ? "text-accent-primary"
                        : "text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    {category.name}
                  </button>
                  {(canUpdate || canDelete) && (
                    <button
                      onClick={() => setModal({ type: "editCategory", category })}
                      aria-label={t("editCategory")}
                      className="hidden h-7 w-7 items-center justify-center rounded text-text-secondary hover:bg-background hover:text-accent-primary group-hover:flex"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </nav>
          ) : (
            <StateView
              kind={categories.type}
              message={categories.type === "error" ? categories.message : undefined}
            />
          )}
        </aside>

        {/* Products pane */}
        <section className="rounded-xl border border-border-default bg-surface p-5">
          <h2 className="text-sm font-semibold text-text-primary">
            {t("products")}
          </h2>

          {products.type === "data" ? (
            products.data.length === 0 ? (
              <StateView kind="empty" message={t("noProducts")} />
            ) : (
              <ul className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {products.data.map((product) => (
                  <li
                    key={product.id}
                    className="flex flex-col justify-between gap-3 rounded-lg border border-border-default bg-background p-4"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-text-primary">
                          {product.name}
                        </p>
                        <button
                          onClick={() => handleToggleAvailable(product)}
                          title={t("available")}
                          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                            product.is_available
                              ? "bg-success"
                              : "bg-text-secondary/40"
                          }`}
                          disabled={!canUpdate}
                        >
                          <span
                            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                              product.is_available ? "translate-x-[4.5px]" : "-translate-x-1"
                            }`}
                          />
                        </button>
                      </div>
                      {product.description && (
                        <p className="mt-1 line-clamp-2 text-xs text-text-secondary">
                          {product.description}
                        </p>
                      )}
                      <p className="mt-2 text-sm font-bold text-accent-primary">
                        {formatMoney(product.price, currency)}
                      </p>
                    </div>
                    {(canUpdate || canDelete) && (
                      <div className="flex items-center justify-end gap-1">
                        {canUpdate && (
                          <button
                            onClick={() =>
                              setModal({ type: "editProduct", product })
                            }
                            aria-label={t("editProduct")}
                            className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-background-secondary hover:text-accent-primary"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        )}
                        {canDelete && (
                          <button
                            onClick={() => setConfirm({ type: "product", target: product })}
                            aria-label={t("deleteProduct")}
                            className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-background-secondary hover:text-error"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )
          ) : (
            <StateView
              kind={products.type}
              message={products.type === "error" ? products.message : undefined}
            />
          )}
        </section>
      </div>

      {modal?.type === "createCategory" && (
        <CategoryFormModal
          title={t("addCategory")}
          onClose={() => setModal(null)}
          onSubmit={(name, desc, order) => handleCreateCategory(name, desc, order)}
        />
      )}

      {modal?.type === "editCategory" && (
        <CategoryFormModal
          title={t("editCategory")}
          initial={modal.category}
          onClose={() => setModal(null)}
          onSubmit={(name, desc, order) =>
            handleUpdateCategory(modal.category, name, desc, order)
          }
        />
      )}

      {modal?.type === "createProduct" && (
        <ProductFormModal
          title={t("addProduct")}
          categories={categories.type === "data" ? categories.data : []}
          defaultCategoryId={selectedCategoryId}
          onClose={() => setModal(null)}
          onSubmit={handleCreateProduct}
        />
      )}

      {modal?.type === "editProduct" && (
        <ProductFormModal
          title={t("editProduct")}
          initial={modal.product}
          categories={categories.type === "data" ? categories.data : []}
          defaultCategoryId={selectedCategoryId}
          onClose={() => setModal(null)}
          onSubmit={(payload) => handleUpdateProduct(modal.product, payload)}
        />
      )}

      {confirm && (
        <Modal
          open
          onClose={() => setConfirm(null)}
          title={
            confirm.type === "category" ? t("deleteCategory") : t("deleteProduct")
          }
        >
          <p className="text-sm text-text-secondary">
            {confirm.type === "category"
              ? t("confirmDeleteCategory")
              : t("confirmDeleteProduct")}
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setConfirm(null)}>
              {tc("actions.cancel")}
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="bg-error hover:brightness-110"
              onClick={() =>
                confirm.type === "category"
                  ? handleDeleteCategory(confirm.target)
                  : handleDeleteProduct(confirm.target)
              }
            >
              {tc("actions.delete")}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Category form
// ---------------------------------------------------------------------------
function CategoryFormModal({
  title,
  initial,
  onClose,
  onSubmit,
}: {
  title: string;
  initial?: CategoryOut;
  onClose: () => void;
  onSubmit: (name: string, description: string, sortOrder: number) => void;
}) {
  const t = useTranslations("menuPage");
  const tc = useTranslations("common");
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [sortOrder, setSortOrder] = useState(String(initial?.sort_order ?? 0));

  return (
    <Modal open onClose={onClose} title={title}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(name.trim(), description.trim(), parseInt(sortOrder, 10) || 0);
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("categoryName")}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("categoryNamePlaceholder")}
            required
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("categoryDescription")}
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("categoryDescriptionPlaceholder")}
            rows={2}
            className="w-full resize-none rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("sortOrder")}
          </label>
          <input
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Product form
// ---------------------------------------------------------------------------
interface ProductFormValues {
  name: string;
  description: string;
  price: string;
  costPrice: string;
  categoryId: string | null;
  available: boolean;
}

function ProductFormModal({
  title,
  initial,
  categories,
  defaultCategoryId,
  onClose,
  onSubmit,
}: {
  title: string;
  initial?: ProductOut;
  categories: CategoryOut[];
  defaultCategoryId: string | null;
  onClose: () => void;
  onSubmit: (values: ProductFormValues) => void;
}) {
  const t = useTranslations("menuPage");
  const tc = useTranslations("common");
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [price, setPrice] = useState(initial?.price ?? "");
  const [costPrice, setCostPrice] = useState(initial?.cost_price ?? "0.00");
  const [categoryId, setCategoryId] = useState<string>(
    initial?.category_id ?? defaultCategoryId ?? ""
  );
  const [available, setAvailable] = useState(initial?.is_available ?? true);

  return (
    <Modal open onClose={onClose} title={title}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({
            name: name.trim(),
            description: description.trim(),
            price,
            costPrice,
            categoryId: categoryId || null,
            available,
          });
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("productName")}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("productNamePlaceholder")}
            required
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("productDescription")}
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("productDescriptionPlaceholder")}
            rows={2}
            className="w-full resize-none rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-text-primary">
              {t("price")}
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
              className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-text-primary">
              {t("costPrice")}
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={costPrice}
              onChange={(e) => setCostPrice(e.target.value)}
              className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("category")}
          </label>
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            <option value="">{t("allCategories")}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <input
            type="checkbox"
            checked={available}
            onChange={(e) => setAvailable(e.target.checked)}
            className="h-4 w-4 rounded border-border-default text-accent-primary"
          />
          {t("available")}
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}