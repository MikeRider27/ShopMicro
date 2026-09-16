"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";
import { useCart } from "./CartProvider";

export default function Navbar() {
  const { user, logout } = useAuth();
  const { count } = useCart();

  return (
    <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-xl font-bold text-brand">
          ShopMicro
        </Link>
        <div className="flex items-center gap-5 text-sm font-medium text-gray-700">
          <Link href="/" className="hover:text-brand">
            Productos
          </Link>
          <Link href="/cart" className="relative hover:text-brand">
            Carrito
            {count > 0 && (
              <span className="absolute -right-3 -top-2 rounded-full bg-brand px-1.5 py-0.5 text-xs text-white">
                {count}
              </span>
            )}
          </Link>
          {user ? (
            <>
              <Link href="/orders" className="hover:text-brand">
                Mis pedidos
              </Link>
              <span className="text-gray-400">|</span>
              <span>Hola, {user.name}</span>
              <button onClick={logout} className="text-red-600 hover:underline">
                Salir
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="hover:text-brand">
                Ingresar
              </Link>
              <Link
                href="/register"
                className="rounded-md bg-brand px-3 py-1.5 text-white hover:bg-brand-dark"
              >
                Registrarse
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
