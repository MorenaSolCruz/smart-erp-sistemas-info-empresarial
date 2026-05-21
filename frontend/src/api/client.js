const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export async function postAgentMessage(payload) {
  const response = await fetch(`${API_BASE_URL}/agent/chat/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "No se pudo procesar la petición.");
  }

  return response.json();
}

export async function getStatistics() {
  const response = await fetch(`${API_BASE_URL}/statistics/overview/`);
  if (!response.ok) {
    throw new Error("No se pudieron cargar las estadísticas.");
  }
  return response.json();
}

async function getResource(path, errorMessage) {
  const response = await fetch(`${API_BASE_URL}${path}`);
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

