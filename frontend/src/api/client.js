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

