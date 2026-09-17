import "@testing-library/jest-dom";

// jsdom no implementa crypto.randomUUID (sí lo hace un navegador real / Node
// en runtime). Lo completamos con el de Node para que lib/api.ts no falle.
if (!global.crypto?.randomUUID) {
  const nodeCrypto = require("crypto");
  Object.defineProperty(global, "crypto", {
    value: { ...global.crypto, randomUUID: () => nodeCrypto.randomUUID() },
  });
}
