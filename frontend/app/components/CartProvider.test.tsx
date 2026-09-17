import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import type { Product } from "@/lib/types";
import { CartProvider, useCart } from "./CartProvider";

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    name: "Producto de prueba",
    description: "",
    price: 10,
    stock: 5,
    image_url: "",
    category: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

const wrapper = ({ children }: { children: ReactNode }) => <CartProvider>{children}</CartProvider>;

beforeEach(() => {
  localStorage.clear();
});

describe("useCart", () => {
  it("empieza vacío", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    expect(result.current.items).toEqual([]);
    expect(result.current.total).toBe(0);
    expect(result.current.count).toBe(0);
  });

  it("agrega un producto nuevo", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.addItem(makeProduct(), 2));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].quantity).toBe(2);
    expect(result.current.total).toBe(20);
    expect(result.current.count).toBe(2);
  });

  it("suma cantidad si el producto ya está en el carrito", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    const product = makeProduct();
    act(() => result.current.addItem(product, 1));
    act(() => result.current.addItem(product, 3));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].quantity).toBe(4);
  });

  it("actualiza la cantidad de un item", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.addItem(makeProduct(), 1));
    act(() => result.current.updateQuantity(1, 5));

    expect(result.current.items[0].quantity).toBe(5);
  });

  it("quita el item si la cantidad baja a 0 o menos", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.addItem(makeProduct(), 1));
    act(() => result.current.updateQuantity(1, 0));

    expect(result.current.items).toEqual([]);
  });

  it("remueve un item puntual", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.addItem(makeProduct({ id: 1 }), 1));
    act(() => result.current.addItem(makeProduct({ id: 2 }), 1));
    act(() => result.current.removeItem(1));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].product.id).toBe(2);
  });

  it("vacía el carrito con clear()", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.addItem(makeProduct(), 1));
    act(() => result.current.clear());

    expect(result.current.items).toEqual([]);
  });

  it("persiste el carrito en localStorage", async () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.addItem(makeProduct(), 2));

    await waitFor(() => {
      const saved = JSON.parse(localStorage.getItem("cart") || "[]");
      expect(saved).toHaveLength(1);
      expect(saved[0].quantity).toBe(2);
    });
  });

  it("calcula el total con varios productos distintos", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.addItem(makeProduct({ id: 1, price: 10 }), 2));
    act(() => result.current.addItem(makeProduct({ id: 2, price: 5 }), 3));

    expect(result.current.total).toBe(35);
    expect(result.current.count).toBe(5);
  });
});
