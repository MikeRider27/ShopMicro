// Validaciones de formulario en el cliente, para dar feedback inmediato sin
// esperar el round-trip al backend. Reflejan las mismas reglas que los
// schemas de Marshmallow del lado del servidor (ver services/*/schemas.py),
// pero no lo reemplazan: el servidor siempre vuelve a validar.

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "El email es requerido.";
  if (!EMAIL_REGEX.test(trimmed)) return "Ingresá un email válido.";
  return null;
}

export function validatePassword(value: string, minLength = 6): string | null {
  if (!value) return "La contraseña es requerida.";
  if (value.length < minLength) return `Debe tener al menos ${minLength} caracteres.`;
  return null;
}

export function validateRequired(value: string, label: string): string | null {
  if (!value.trim()) return `${label} es requerido.`;
  return null;
}

/** Corre varios validadores y devuelve solo los que fallaron, indexados por campo. */
export function collectErrors(
  fields: Record<string, () => string | null>
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const [field, validate] of Object.entries(fields)) {
    const error = validate();
    if (error) errors[field] = error;
  }
  return errors;
}
