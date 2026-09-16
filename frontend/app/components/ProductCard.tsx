"use client";

import Image from "next/image";
import Link from "next/link";
import type { Product } from "@/lib/types";
import { useCart } from "./CartProvider";

export default function ProductCard({ product }: { product: Product }) {
  const { addItem } = useCart();

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm transition hover:shadow-md">
      <Link href={`/products/${product.id}`} className="relative aspect-square bg-gray-100">
        {product.image_url ? (
          <Image
            src={product.image_url}
            alt={product.name}
            fill
            className="object-cover"
            sizes="(max-width: 768px) 50vw, 25vw"
          />
        ) : null}
      </Link>
      <div className="flex flex-1 flex-col gap-1 p-4">
        <Link href={`/products/${product.id}`} className="font-semibold text-gray-900 hover:text-brand">
          {product.name}
        </Link>
        {product.category && (
          <span className="text-xs uppercase tracking-wide text-gray-400">{product.category.name}</span>
        )}
        <p className="mt-auto flex items-center justify-between pt-2">
          <span className="text-lg font-bold text-gray-900">${product.price.toFixed(2)}</span>
          <button
            onClick={() => addItem(product, 1)}
            disabled={product.stock <= 0}
            className="rounded-md bg-brand px-3 py-1.5 text-sm text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            {product.stock > 0 ? "Agregar" : "Sin stock"}
          </button>
        </p>
      </div>
    </div>
  );
}
