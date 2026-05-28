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
      "Hola, soy Maja. Puedo ayudarte a gestionar el ERP por conversacion. Por ejemplo: 'que productos tengo', 'cuantos monitores tengo', 'introduce 23 unidades de memoria ram al inventario', 'registra un proveedor llamado TecnoSur con email contacto@tecnosur.com', 'muestrame estadisticas' o 'pon modo oscuro'.",
    meta: "Asistente operativo | Control por conversacion",
  },
];

const actionLabels = {
  list_products: "Consulta de productos",
  create_product: "Alta de producto",
  add_product_stock: "Entrada de inventario",
  get_product_stock: "Consulta de stock",
  update_product: "Actualizacion de producto",
  delete_product: "Baja de producto",
  delete_all_products: "Baja completa de inventario",
  query_products: "Consulta avanzada de inventario",
  list_suppliers: "Consulta de proveedores",
  create_supplier: "Alta de proveedor",
  update_supplier: "Actualizacion de proveedor",
  delete_supplier: "Baja de proveedor",
  delete_all_suppliers: "Baja completa de proveedores",
  list_purchase_orders: "Consulta de pedidos",
  create_purchase_order: "Alta de pedido",
  update_purchase_order: "Actualizacion de pedido",
  delete_purchase_order: "Baja de pedido",
  query_purchase_orders: "Consulta avanzada de pedidos",
  complete_purchase_order: "Actualizacion de pedido",
  cancel_latest_purchase_order: "Cancelacion de pedido",
  list_waste: "Consulta de desechos",
  create_waste: "Registro de desecho",
  update_waste: "Actualizacion de desecho",
  delete_waste: "Baja de desecho",
  delete_all_waste: "Baja completa de desechos",
  show_statistics: "Analisis estadistico",
  show_audit_history: "Trazabilidad",
  configure_auto_replenishment: "Reposicion automatica",
  help: "Ayuda operativa",
  confirmation_required: "Confirmacion requerida",
  missing_data: "Datos incompletos",
  fallback: "Sin accion ejecutada",
};

const providerNotes = {
  "gemini-2.5-flash": "Modelo equilibrado para operaciones del ERP.",
  "gemini-2.5-flash-lite": "Modelo ligero para respuestas rapidas.",
  "gemini-2.0-flash": "Modelo rapido de generacion anterior.",
};

function normalizeMessage(message) {
  return message.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function detectThemeCommand(message) {
  const normalized = normalizeMessage(message);
  const wantsThemeChange = ["modo", "tema", "theme", "oscuro", "claro", "dark", "light"].some((term) =>
    normalized.includes(term),
  );
  const hasActionVerb = ["pon", "cambia", "cambiar", "activa", "activar", "usa"].some((term) =>
    normalized.includes(term),
  );

  if (!wantsThemeChange || !hasActionVerb) {
    return null;
  }

  if (["oscuro", "dark"].some((term) => normalized.includes(term))) {
    return "dark";
  }

  if (["claro", "light"].some((term) => normalized.includes(term))) {
    return "light";
  }

  return null;
}

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

  const applyTheme = (nextTheme) => {
    setTheme(nextTheme);
    localStorage.setItem("erp-theme", nextTheme);
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
      delete_all_suppliers: ["Proveedores actualizados", getSuppliers],
      list_purchase_orders: ["Pedidos actualizados", getPurchaseOrders],
      create_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      update_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      delete_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      complete_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      cancel_latest_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      list_waste: ["Desechos actualizados", getWasteRecords],
      create_waste: ["Desechos actualizados", getWasteRecords],
      update_waste: ["Desechos actualizados", getWasteRecords],
      delete_waste: ["Desechos actualizados", getWasteRecords],
      delete_all_waste: ["Desechos actualizados", getWasteRecords],
      show_statistics: ["Resumen operativo", getStatistics],
    };

    const panel = dashboardByAction[action];
    if (!panel) {
      return false;
    }

    const [nextTitle, loader] = panel;
    setPanelRefreshing(true);
    try {
      const freshData = await loader();
      setResultData(freshData);
      setPanelTitle(nextTitle);
    } catch {
      // The chat response still remains available if the live panel refresh fails.
      return false;
    } finally {
      setPanelRefreshing(false);
    }
    return true;
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
      const normalizedMessage = normalizeMessage(userMessage);
      const requestedTheme = detectThemeCommand(userMessage);

      if (requestedTheme) {
        applyTheme(requestedTheme);
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content:
              requestedTheme === "dark"
                ? "Activo el modo oscuro en la interfaz."
                : "Activo el modo claro en la interfaz.",
            meta: "Completado | Cambio de tema | Interfaz",
          },
        ]);
        return;
      }

      if (pendingAction && ["no", "n", "cancelar"].includes(normalizedMessage)) {
        setPendingAction(null);
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: "Operacion cancelada. El inventario se mantiene sin cambios.",
            meta: "Cancelado | Baja completa de inventario",
          },
        ]);
        return;
      }

      const outgoingMessage =
        pendingAction && ["si", "s", "yes"].includes(normalizedMessage)
          ? pendingAction.confirmation_token || "confirma eliminar todo el inventario"
          : userMessage;

      const response = await postAgentMessage({ message: outgoingMessage, provider });
      const actionLabel = actionLabels[response.action] || "Operacion ERP";
      const providerDetail = response.provider_status ? ` | ${response.provider_status}` : "";

      if (response.action === "confirmation_required" && response.data?.pending_action) {
        setPendingAction(response.data);
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

      const directPanelTitles = {
        show_audit_history: "Trazabilidad",
        configure_auto_replenishment: "Reposicion automatica",
      };

      if (directPanelTitles[response.action] && response.data) {
        setPanelTitle(directPanelTitles[response.action]);
        setResultData(response.data);
      } else {
        const panelWasRefreshed = await refreshPanel(response.action);
        if (!panelWasRefreshed && response.data) {
          setPanelTitle(actionLabel);
          setResultData(response.data);
        }
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: error.message,
          meta: "Error al procesar la peticion",
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
            Todo se gestiona por chat, como una conversacion natural con el asistente.
          </p>

          <div className="topbar-controls">
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
                <h2>Gestiona el almacen por conversacion</h2>
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
