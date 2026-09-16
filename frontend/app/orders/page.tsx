"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Order } from "@/lib/types";
import { useAuth } from "../components/AuthProvider";

export default function OrdersPage() {
  return (
    <Suspense fallback={<p className="text-gray-500">Cargando...</p>}>
      <OrdersContent />
    </Suspense>
  );
}

function OrdersContent() {
  const { user, token } = useAuth();
  const searchParams = useSearchParams();
  const confirmed = searchParams.get("confirmed");
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .listOrders(token)
      .then((r) => setOrders(r.orders))
      .catch(() => setError("No se pudieron cargar tus pedidos."))
      .finally(() => setLoading(false));
  }, [token]);

  if (!user) {
    return (
      <div className="text-center">
        <p className="text-gray-600">Debes iniciar sesión para ver tus pedidos.</p>
        <Link href="/login" className="mt-4 inline-block text-brand hover:underline">
          Ingresar
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Mis pedidos</h1>

      {confirmed && (
        <p className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700">
          ¡Pedido #{confirmed} confirmado con éxito!
        </p>
      )}
      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</p>}
      {loading && <p className="text-gray-500">Cargando...</p>}
      {!loading && orders.length === 0 && <p className="text-gray-500">Aún no tienes pedidos.</p>}

      <div className="flex flex-col gap-4">
        {orders.map((order) => (
          <div key={order.id} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="font-semibold">Pedido #{order.id}</span>
              <span className="text-sm text-gray-500">
                {new Date(order.created_at).toLocaleString()}
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Envío a: {order.shipping_address}</p>
            <div className="mt-3 flex flex-col gap-1">
              {order.items.map((item) => (
                <div key={item.product_id} className="flex justify-between text-sm">
                  <span>
                    {item.product_name} × {item.quantity}
                  </span>
                  <span>${item.subtotal.toFixed(2)}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 flex justify-between border-t border-gray-200 pt-2 font-semibold">
              <span>Total</span>
              <span>${order.total.toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
