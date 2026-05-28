const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

function delay(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function fetchWithRetry(url, options = {}, retries = 1) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (retries <= 0 || error?.name !== "TypeError") {
      throw error;
    }
    await delay(700);
    return fetchWithRetry(url, options, retries - 1);
  }
}

export async function postAgentMessage(payload) {
  const response = await fetchWithRetry(
    `${API_BASE_URL}/agent/chat/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
    1,
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "No se pudo procesar la peticion.");
  }

  return response.json();
}

export async function getStatistics() {
  const response = await fetchWithRetry(`${API_BASE_URL}/statistics/overview/`, {}, 1);
  if (!response.ok) {
    throw new Error("No se pudieron cargar las estadisticas.");
  }
  return response.json();
}

export async function pingBackend() {
  const response = await fetchWithRetry(`${API_BASE_URL}/agent/metrics/`, {}, 1);
  if (!response.ok) {
    throw new Error("El backend todavia no esta disponible.");
  }
  return response.json();
}

async function getResource(path, errorMessage) {
  const response = await fetchWithRetry(`${API_BASE_URL}${path}`, {}, 1);
  if (!response.ok) {
    throw new Error(errorMessage);
  }
  return response.json();
}

export function getProducts() {
  return getResource("/products/", "No se pudo actualizar el inventario.");
}

export function getSuppliers() {
  return getResource("/suppliers/", "No se pudieron actualizar los proveedores.");
}

export function getPurchaseOrders() {
  return getResource("/purchase-orders/", "No se pudieron actualizar los pedidos.");
}

export function getWasteRecords() {
  return getResource("/waste/", "No se pudieron actualizar los desechos.");
}
