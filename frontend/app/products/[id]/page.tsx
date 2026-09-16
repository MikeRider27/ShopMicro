"use client";

import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Product } from "@/lib/types";
import { useCart } from "../../components/CartProvider";

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { addItem } = useCart();
  const [product, setProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getProduct(Number(params.id))
      .then((r) => setProduct(r.product))
      .catch(() => setError("Producto no encontrado."));
  }, [params.id]);

  if (error) {
    return <p className="rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</p>;
  }
  if (!product) {
    return <p className="text-gray-500">Cargando...</p>;
  }

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <div className="relative aspect-square overflow-hidden rounded-lg bg-gray-100">
        {product.image_url && (
          <Image src={product.image_url} alt={product.name} fill className="object-cover" />
        )}
      </div>
      <div>
        {product.category && (
          <span className="text-xs uppercase tracking-wide text-gray-400">{product.category.name}</span>
        )}
        <h1 className="mt-1 text-2xl font-bold">{product.name}</h1>
        <p className="mt-3 text-gray-600">{product.description}</p>
        <p className="mt-4 text-3xl font-bold text-gray-900">${product.price.toFixed(2)}</p>
        <p className="mt-1 text-sm text-gray-500">
          {product.stock > 0 ? `${product.stock} disponibles` : "Sin stock"}
        </p>

        <div className="mt-6 flex items-center gap-3">
          <input
            type="number"
            min={1}
            max={product.stock}
            value={quantity}
            onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
            className="w-20 rounded-md border border-gray-300 px-3 py-2"
          />
          <button
            disabled={product.stock <= 0}
            onClick={() => {
              addItem(product, quantity);
              router.push("/cart");
            }}
            className="rounded-md bg-brand px-5 py-2 font-medium text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            Agregar al carrito
          </button>
        </div>
      </div>
    </div>
  );
}
