"use client";

import Image from "next/image";
import Link from "next/link";
import { useCart } from "../components/CartProvider";

export default function CartPage() {
  const { items, removeItem, updateQuantity, total } = useCart();

  if (items.length === 0) {
    return (
      <div className="text-center">
        <p className="text-gray-500">Tu carrito está vacío.</p>
        <Link href="/" className="mt-4 inline-block text-brand hover:underline">
          Ver productos
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Carrito</h1>
      <div className="flex flex-col gap-4">
        {items.map(({ product, quantity }) => (
          <div key={product.id} className="flex items-center gap-4 rounded-lg border border-gray-200 bg-white p-4">
            <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-md bg-gray-100">
              {product.image_url && (
                <Image src={product.image_url} alt={product.name} fill className="object-cover" />
              )}
            </div>
            <div className="flex-1">
              <p className="font-semibold">{product.name}</p>
              <p className="text-sm text-gray-500">${product.price.toFixed(2)} c/u</p>
            </div>
            <input
              type="number"
              min={1}
              max={product.stock}
              value={quantity}
              onChange={(e) => updateQuantity(product.id, Number(e.target.value))}
              className="w-16 rounded-md border border-gray-300 px-2 py-1"
            />
            <p className="w-20 text-right font-semibold">${(product.price * quantity).toFixed(2)}</p>
            <button
              onClick={() => removeItem(product.id)}
              className="text-sm text-red-600 hover:underline"
            >
              Quitar
            </button>
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between rounded-lg bg-gray-50 p-4">
        <span className="text-lg font-semibold">Total: ${total.toFixed(2)}</span>
        <Link
          href="/checkout"
          className="rounded-md bg-brand px-5 py-2 font-medium text-white hover:bg-brand-dark"
        >
          Ir a pagar
        </Link>
      </div>
    </div>
  );
}
