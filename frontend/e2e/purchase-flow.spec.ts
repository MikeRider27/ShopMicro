import { expect, test } from "@playwright/test";

// Flujo completo: registro -> login (implícito, register ya loguea) ->
// ver productos -> agregar al carrito -> checkout -> ver el pedido en el
// historial. Corre contra el stack real (frontend + gateway + los 3
// microservicios), no mockea nada.

test("registro, compra y verificación en el historial", async ({ page }) => {
  const uniqueEmail = `e2e-${Date.now()}@example.com`;
  const password = "e2e-secret-123";

  // 1. Registro
  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Usuario E2E");
  await page.getByLabel("Email").fill(uniqueEmail);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  // El registro loguea automáticamente y redirige al catálogo.
  await expect(page).toHaveURL("/");
  await expect(page.getByText("Hola, Usuario E2E")).toBeVisible();

  // 2. Ver productos (catálogo sembrado por product-service)
  const firstProductCard = page.locator("a[href^='/products/']").first();
  await expect(firstProductCard).toBeVisible();
  const productName = await firstProductCard.textContent();

  // 3. Agregar al carrito
  await page
    .getByRole("button", { name: "Agregar" })
    .first()
    .click();
  await expect(page.getByText("1", { exact: true })).toBeVisible(); // badge del carrito

  // 4. Ir al carrito
  await page.getByRole("link", { name: /Carrito/ }).click();
  await expect(page).toHaveURL("/cart");
  if (productName) {
    await expect(page.getByText(productName.trim(), { exact: false })).toBeVisible();
  }

  // 5. Checkout
  await page.getByRole("link", { name: "Ir a pagar" }).click();
  await expect(page).toHaveURL("/checkout");
  await page.getByLabel("Dirección de envío").fill("Calle Falsa 123, Springfield");
  await page.getByRole("button", { name: "Confirmar pedido" }).click();

  // 6. Confirmación y verificación en el historial
  await expect(page).toHaveURL(/\/orders\?confirmed=\d+/);
  await expect(page.getByText(/confirmado con éxito/)).toBeVisible();
  await expect(page.getByText(/Pedido #\d+/).first()).toBeVisible();
});

test("checkout sin sesión redirige a pedir login", async ({ page }) => {
  await page.goto("/checkout");
  await expect(page.getByText("Debes iniciar sesión para completar tu compra.")).toBeVisible();
});

test("muestra error de validación con email inválido en el registro", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Usuario Test");
  await page.getByLabel("Email").fill("no-es-un-email");
  await page.getByLabel("Contraseña").fill("secret123");
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  // La validación de cliente bloquea el submit antes de llamar a la API.
  await expect(page.getByText("Ingresá un email válido.")).toBeVisible();
  await expect(page).toHaveURL("/register");
});
