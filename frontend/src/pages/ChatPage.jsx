import { useEffect, useState } from "react";

import {
  getProducts,
  getPurchaseOrders,
  getStatistics,
  getSuppliers,
  getWasteRecords,
  postAgentMessage,
} from "../api/client";
import ChatMessage from "../components/ChatMessage";
import DataPanel from "../components/DataPanel";

const initialMessages = [
  {
    role: "assistant",
    content:
      "Hola, soy Maja. Puedo ayudarte a gestionar el ERP por conversación. Por ejemplo: 'qué productos tengo', 'cuántos monitores tengo', 'introduce 23 unidades de memoria ram al inventario', 'registra un proveedor llamado TecnoSur con email contacto@tecnosur.com' o 'muéstrame estadísticas'.",
    meta: "Asistente operativo | Control por conversación",
  },
];

const actionLabels = {
  list_products: "Consulta de productos",
  create_product: "Alta de producto",
  add_product_stock: "Entrada de inventario",
  get_product_stock: "Consulta de stock",
  update_product: "Actualización de producto",
  delete_product: "Baja de producto",
  delete_all_products: "Baja completa de inventario",
  list_suppliers: "Consulta de proveedores",
  create_supplier: "Alta de proveedor",
  update_supplier: "Actualización de proveedor",
  delete_supplier: "Baja de proveedor",
  list_purchase_orders: "Consulta de pedidos",
  create_purchase_order: "Alta de pedido",
  update_purchase_order: "Actualización de pedido",
  delete_purchase_order: "Baja de pedido",
  list_waste: "Consulta de desechos",
  create_waste: "Registro de desecho",
  update_waste: "Actualización de desecho",
  delete_waste: "Baja de desecho",
  show_statistics: "Análisis estadístico",
  help: "Ayuda operativa",
  confirmation_required: "Confirmación requerida",
  missing_data: "Datos incompletos",
  fallback: "Sin acción ejecutada",
};

const providerNotes = {
  "gemini-2.5-flash": "Modelo equilibrado para operaciones del ERP.",
  "gemini-2.5-flash-lite": "Modelo ligero para respuestas rápidas.",
  "gemini-2.0-flash": "Modelo rápido de generación anterior.",
};

export default function ChatPage() {
  const defaultGeminiModel = import.meta.env.VITE_DEFAULT_LLM_PROVIDER?.startsWith("gemini")
    ? import.meta.env.VITE_DEFAULT_LLM_PROVIDER
    : "gemini-2.5-flash";
  const [provider, setProvider] = useState(defaultGeminiModel);
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultData, setResultData] = useState(null);
  const [panelTitle, setPanelTitle] = useState("Resumen operativo");
  const [panelRefreshing, setPanelRefreshing] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("erp-theme") || "light");
  const [pendingAction, setPendingAction] = useState(null);

  useEffect(() => {
    refreshPanel("show_statistics");
  }, []);

  const toggleTheme = () => {
    setTheme((currentTheme) => {
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      localStorage.setItem("erp-theme", nextTheme);
      return nextTheme;
    });
  };

  const refreshPanel = async (action) => {
    const dashboardByAction = {
      list_products: ["Inventario actualizado", getProducts],
      create_product: ["Inventario actualizado", getProducts],
      add_product_stock: ["Inventario en vivo", getProducts],
      update_product: ["Inventario actualizado", getProducts],
      delete_product: ["Inventario actualizado", getProducts],
      delete_all_products: ["Inventario actualizado", getProducts],
      get_product_stock: ["Inventario en vivo", getProducts],
      list_suppliers: ["Proveedores actualizados", getSuppliers],
      create_supplier: ["Proveedores actualizados", getSuppliers],
      update_supplier: ["Proveedores actualizados", getSuppliers],
      delete_supplier: ["Proveedores actualizados", getSuppliers],
      list_purchase_orders: ["Pedidos actualizados", getPurchaseOrders],
      create_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      update_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      delete_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      list_waste: ["Desechos actualizados", getWasteRecords],
      create_waste: ["Desechos actualizados", getWasteRecords],
      update_waste: ["Desechos actualizados", getWasteRecords],
      delete_waste: ["Desechos actualizados", getWasteRecords],
      show_statistics: ["Resumen operativo", getStatistics],
    };

    const panel = dashboardByAction[action];
    if (!panel) {
      return;
    }

    const [nextTitle, loader] = panel;
    setPanelRefreshing(true);
    try {
      const freshData = await loader();
      setResultData(freshData);
      setPanelTitle(nextTitle);
    } catch {
      // The chat response still remains available if the live panel refresh fails.
    } finally {
      setPanelRefreshing(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!input.trim() || loading) {
      return;
    }

    const userMessage = input.trim();
    setMessages((current) => [...current, { role: "user", content: userMessage }]);
    setInput("");
    setLoading(true);

    try {
      const normalizedMessage = userMessage.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
      if (pendingAction === "delete_all_products" && ["no", "n", "cancelar"].includes(normalizedMessage)) {
        setPendingAction(null);
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: "Operación cancelada. El inventario se mantiene sin cambios.",
            meta: "Cancelado | Baja completa de inventario",
          },
        ]);
        return;
      }

      const outgoingMessage =
        pendingAction === "delete_all_products" && ["si", "s", "yes"].includes(normalizedMessage)
          ? "confirma eliminar todo el inventario"
          : userMessage;

      const response = await postAgentMessage({ message: outgoingMessage, provider });
      const actionLabel = actionLabels[response.action] || "Operación ERP";
      const providerDetail = response.provider_status ? ` | ${response.provider_status}` : "";
      if (response.action === "confirmation_required" && response.data?.pending_action) {
        setPendingAction(response.data.pending_action);
      } else {
        setPendingAction(null);
      }
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.reply,
          meta: `${response.success ? "Completado" : "Revisar"} | ${actionLabel} | Proveedor ${response.provider}${providerDetail}`,
        },
      ]);
      await refreshPanel(response.action);
      if (!response.action?.startsWith("list_") && response.action !== "show_statistics" && response.data) {
        setResultData((currentData) => currentData || response.data);
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: error.message,
          meta: "Error al procesar la petición",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleComposerKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  };

  return (
    <main className={`layout theme-${theme}`}>
      <section className="app-shell">
        <header className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div>
              <p className="eyebrow">Asistente de inventario</p>
              <h1>Maja ERP</h1>
            </div>
          </div>

          <p className="topbar-copy">
            Todo se gestiona por chat, como una conversación natural con el asistente.
          </p>

          <div className="topbar-controls">
            <button
              className="theme-toggle"
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Activar modo claro" : "Activar modo oscuro"}
              title={theme === "dark" ? "Modo claro" : "Modo oscuro"}
            >
              <span className="bulb-icon" aria-hidden="true" />
            </button>

            <label className="provider-box">
              <span>Modelo Gemini</span>
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                <option value="gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</option>
                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
              </select>
              <small>{providerNotes[provider]}</small>
            </label>

          </div>
        </header>

        <div className="content-grid">
          <section className="conversation-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Chat operativo</p>
                <h2>Gestiona el almacén por conversación</h2>
              </div>
              <div className={`status-dot ${loading ? "status-busy" : ""}`}>
                {loading ? "Procesando" : "Operativo"}
              </div>
            </div>

            <div className="messages">
              {messages.map((message, index) => (
                <ChatMessage
                  key={`${message.role}-${index}`}
                  role={message.role}
                  content={message.content}
                  meta={message.meta}
                />
              ))}
              {loading ? <ChatMessage role="assistant" thinking meta="Analizando orden y consultando el ERP" /> : null}
            </div>

            <form className="composer" onSubmit={handleSubmit}>
              <label className="composer-label" htmlFor="jarvis-order">
                Enviar orden a Maja
              </label>
              <input
                id="jarvis-order"
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="Escribe una orden para Maja..."
              />
              <button type="submit" disabled={loading}>
                {loading ? "Procesando..." : "Enviar"}
              </button>
            </form>
          </section>

          <aside className="data-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Salida</p>
                <h2>{panelTitle}</h2>
              </div>
              {panelRefreshing ? <span className="panel-sync">Actualizando</span> : null}
            </div>
            <DataPanel data={resultData} title={panelTitle} isRefreshing={panelRefreshing} />
          </aside>
        </div>
      </section>
    </main>
  );
}

