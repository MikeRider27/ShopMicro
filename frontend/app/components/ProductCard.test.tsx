import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Product } from "@/lib/types";
import { CartProvider, useCart } from "./CartProvider";
import ProductCard from "./ProductCard";

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    name: "Auriculares Bluetooth",
    description: "",
    price: 29.99,
    stock: 5,
    image_url: "",
    category: { id: 1, name: "Electrónica" },
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function CartCount() {
  const { count } = useCart();
  return <span data-testid="cart-count">{count}</span>;
}

function renderWithCart(product: Product) {
  return render(
    <CartProvider>
      <ProductCard product={product} />
      <CartCount />
    </CartProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe("ProductCard", () => {
  it("muestra nombre, categoría y precio", () => {
    renderWithCart(makeProduct());
    expect(screen.getByText("Auriculares Bluetooth")).toBeInTheDocument();
    expect(screen.getByText("Electrónica")).toBeInTheDocument();
    expect(screen.getByText("$29.99")).toBeInTheDocument();
  });

  it("agrega el producto al carrito al hacer click en 'Agregar'", async () => {
    const user = userEvent.setup();
    renderWithCart(makeProduct());

    await user.click(screen.getByRole("button", { name: "Agregar" }));

    expect(screen.getByTestId("cart-count").textContent).toBe("1");
  });

  it("deshabilita el botón y muestra 'Sin stock' cuando stock es 0", () => {
    renderWithCart(makeProduct({ stock: 0 }));

    const button = screen.getByRole("button", { name: "Sin stock" });
    expect(button).toBeDisabled();
  });
});
