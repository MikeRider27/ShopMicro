import { ApiError, api } from "./api";

function mockFetchOnce(status: number, body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as unknown as typeof fetch;
}

const originalLocation = window.location;

beforeEach(() => {
  localStorage.clear();
  // jsdom no implementa navegación real; reemplazamos location para poder
  // observar el redirect a /login sin que tire "Not implemented".
  // @ts-expect-error -- reasignación intencional solo para el test
  delete window.location;
  // @ts-expect-error -- misma razón
  window.location = { href: "" };
});

afterEach(() => {
  window.location = originalLocation;
  jest.restoreAllMocks();
});

describe("api / request()", () => {
  it("devuelve los datos cuando la respuesta es exitosa", async () => {
    mockFetchOnce(200, { products: [] });
    const result = await api.listProducts();
    expect(result).toEqual({ products: [] });
  });

  it("lanza ApiError con code/message del backend en un error de negocio", async () => {
    mockFetchOnce(409, { error: { code: "EMAIL_ALREADY_REGISTERED", message: "el email ya está registrado" } });

    await expect(
      api.register({ email: "a@a.com", password: "secret123", name: "A" })
    ).rejects.toMatchObject({
      message: "el email ya está registrado",
      code: "EMAIL_ALREADY_REGISTERED",
    });
  });

  it("lanza un ApiError amigable si fetch rechaza (sin conexión)", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.listProducts()).rejects.toBeInstanceOf(ApiError);
    await expect(api.listProducts()).rejects.toMatchObject({
      message: expect.stringContaining("conexión"),
    });
  });

  it("en un 401 con token, limpia la sesión y redirige a /login con motivo", async () => {
    localStorage.setItem("token", "stale-token");
    localStorage.setItem("user", JSON.stringify({ id: 1, name: "X" }));
    mockFetchOnce(401, { error: { code: "TOKEN_EXPIRED", message: "el token expiró" } });

    await expect(api.me("stale-token")).rejects.toMatchObject({ code: "SESSION_EXPIRED" });

    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("user")).toBeNull();
    expect(window.location.href).toBe("/login?reason=session_expired");
  });

  it("un 401 sin token (login con credenciales inválidas) NO redirige", async () => {
    mockFetchOnce(401, { error: { code: "INVALID_CREDENTIALS", message: "credenciales inválidas" } });

    await expect(api.login({ email: "a@a.com", password: "mala" })).rejects.toMatchObject({
      code: "INVALID_CREDENTIALS",
    });
    expect(window.location.href).toBe("");
  });
});
