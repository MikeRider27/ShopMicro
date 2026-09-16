"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "../components/AuthProvider";
import { useCart } from "../components/CartProvider";

export default function CheckoutPage() {
  const { user, token } = useAuth();
  const { items, total, clear } = useCart();
  const router = useRouter();
  const [address, setAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!user || !token) {
    return (
      <div className="text-center">
        <p className="text-gray-600">Debes iniciar sesión para completar tu compra.</p>
        <Link href="/login" className="mt-4 inline-block text-brand hover:underline">
          Ingresar
        </Link>
      </div>
    );
  }

  if (items.length === 0) {
    return <p className="text-gray-500">Tu carrito está vacío.</p>;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { order } = await api.createOrder(
        {
          items: items.map((i) => ({ product_id: i.product.id, quantity: i.quantity })),
          shipping_address: address,
        },
        token
      );
      clear();
      router.push(`/orders?confirmed=${order.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el pedido.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-6 text-2xl font-bold">Finalizar compra</h1>

      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
        {items.map((i) => (
          <div key={i.product.id} className="flex justify-between py-1 text-sm">
            <span>
              {i.product.name} × {i.quantity}
            </span>
            <span>${(i.product.price * i.quantity).toFixed(2)}</span>
          </div>
        ))}
        <div className="mt-2 flex justify-between border-t border-gray-200 pt-2 font-semibold">
          <span>Total</span>
          <span>${total.toFixed(2)}</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="text-sm font-medium text-gray-700">
          Dirección de envío
          <textarea
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
            rows={3}
          />
        </label>

        {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-brand px-5 py-2 font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {loading ? "Procesando..." : "Confirmar pedido"}
        </button>
      </form>
    </div>
  );
}
