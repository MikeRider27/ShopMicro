import { collectErrors, validateEmail, validatePassword, validateRequired } from "./validation";

describe("validateEmail", () => {
  it("rechaza vacío", () => {
    expect(validateEmail("")).toMatch(/requerido/);
  });

  it("rechaza formato inválido", () => {
    expect(validateEmail("no-es-un-email")).toMatch(/válido/);
  });

  it("acepta un email válido", () => {
    expect(validateEmail("user@example.com")).toBeNull();
  });

  it("recorta espacios antes de validar", () => {
    expect(validateEmail("  user@example.com  ")).toBeNull();
  });
});

describe("validatePassword", () => {
  it("rechaza vacío", () => {
    expect(validatePassword("")).toMatch(/requerida/);
  });

  it("rechaza contraseñas cortas", () => {
    expect(validatePassword("123")).toMatch(/al menos/);
  });

  it("acepta una contraseña de longitud suficiente", () => {
    expect(validatePassword("secret123")).toBeNull();
  });
});

describe("validateRequired", () => {
  it("rechaza vacío o solo espacios", () => {
    expect(validateRequired("", "El nombre")).toBe("El nombre es requerido.");
    expect(validateRequired("   ", "El nombre")).toBe("El nombre es requerido.");
  });

  it("acepta un valor no vacío", () => {
    expect(validateRequired("Ana", "El nombre")).toBeNull();
  });
});

describe("collectErrors", () => {
  it("solo incluye los campos que fallaron", () => {
    const errors = collectErrors({
      email: () => validateEmail("mal-formado"),
      password: () => validatePassword("secret123"),
    });
    expect(Object.keys(errors)).toEqual(["email"]);
  });

  it("devuelve un objeto vacío si todo pasa", () => {
    const errors = collectErrors({
      email: () => validateEmail("user@example.com"),
    });
    expect(errors).toEqual({});
  });
});
