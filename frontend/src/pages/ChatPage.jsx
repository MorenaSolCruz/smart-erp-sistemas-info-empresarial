import { useEffect, useState } from "react";

import {
  getProducts,
  getPurchaseOrders,
  getStatistics,
  pingBackend,
  getSuppliers,
  getWasteRecords,
  postAgentMessage,
} from "../api/client";
import ChatMessage from "../components/ChatMessage";
import DataPanel from "../components/DataPanel";

const initialMessages = [
  // Mensaje inicial que orienta al usuario sobre ordenes posibles del ERP.
  {
    role: "assistant",
    content:
      "Hola, soy Maja. Puedo ayudarte a gestionar el ERP por conversacion. Por ejemplo: 'que productos tengo', 'cuantos monitores tengo', 'introduce 23 unidades de memoria ram al inventario', 'registra un proveedor llamado TecnoSur con email contacto@tecnosur.com', 'muestrame estadisticas' o 'pon modo oscuro'.",
    meta: "Asistente operativo | Control por conversacion",
  },
];

const actionLabels = {
  // Traduce las acciones internas del backend a etiquetas legibles en la interfaz.
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
  receive_purchase_order: "Recepcion de pedido",
  cancel_purchase_order: "Cancelacion de pedido",
  update_purchase_order: "Actualizacion de pedido",
  delete_purchase_order: "Baja de pedido",
  delete_all_purchase_orders: "Baja completa de pedidos",
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

const cancellationMessages = {
  // Respuestas locales cuando el usuario cancela una accion pendiente de confirmacion.
  delete_supplier: "Operacion cancelada. El proveedor se mantiene sin cambios.",
  update_purchase_order: "Operacion cancelada. El pedido no ha sido modificado.",
  delete_purchase_order: "Operacion cancelada. El pedido se mantiene registrado.",
  cancel_purchase_order: "Operacion cancelada. El pedido sigue abierto sin cambios.",
  delete_all_products: "Operacion cancelada. El inventario se mantiene sin cambios.",
  delete_all_suppliers: "Operacion cancelada. Los proveedores se mantienen sin cambios.",
  delete_all_purchase_orders: "Operacion cancelada. Los pedidos se mantienen registrados.",
  delete_all_waste: "Operacion cancelada. Los desechos se mantienen sin cambios.",
};

const providerNotes = {
  // Texto de ayuda para el selector de proveedor LLM.
  mock: "Modo de demostracion sin llamadas a APIs externas.",
  gemini: "Usa Gemini si la clave API esta configurada.",
  "gemini-2.5-flash": "Modelo equilibrado para operaciones del ERP.",
  "gemini-2.5-flash-lite": "Modelo ligero para respuestas rapidas.",
  "gemini-2.0-flash": "Modelo rapido de generacion anterior.",
};

function normalizeMessage(message) {
  // Normaliza texto del usuario para comparar comandos sin depender de tildes.
  return message.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function detectThemeCommand(message) {
  // Detecta ordenes locales de tema claro/oscuro sin consultar al backend.
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
  // Pantalla principal: combina chat, selector LLM, estado del backend y panel de datos.
  const defaultProvider = import.meta.env.VITE_DEFAULT_LLM_PROVIDER || "gemini-2.5-flash";
  // Estados principales de React:
  // - provider: decide que LLM usa el backend.
  // - messages/input/loading: controlan la conversacion.
  // - resultData/panelTitle: alimentan el panel derecho.
  // - pendingAction: guarda acciones que esperan confirmacion "si/no".
  // - backendReady/backendChecking: evitan mandar ordenes si Django aun arranca.
  const [provider, setProvider] = useState(defaultProvider);
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultData, setResultData] = useState(null);
  const [panelTitle, setPanelTitle] = useState("Resumen operativo");
  const [panelRefreshing, setPanelRefreshing] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("erp-theme") || "light");
  const [pendingAction, setPendingAction] = useState(null);
  const [backendReady, setBackendReady] = useState(false);
  const [backendChecking, setBackendChecking] = useState(true);

  useEffect(() => {
    // Al cargar la pantalla, comprueba backend y muestra estadisticas iniciales.
    const initializeBackend = async () => {
      try {
        await pingBackend();
        setBackendReady(true);
      } catch {
        setBackendReady(false);
      } finally {
        setBackendChecking(false);
      }
    };

    initializeBackend();
    refreshPanel("show_statistics");
  }, []);

  const applyTheme = (nextTheme) => {
    // Guarda el tema visual para que se mantenga al recargar la pagina.
    setTheme(nextTheme);
    localStorage.setItem("erp-theme", nextTheme);
  };

  const refreshPanel = async (action) => {
    // Segun la accion ejecutada, decide que endpoint refresca el panel lateral.
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
      receive_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      cancel_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      update_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      delete_purchase_order: ["Pedidos actualizados", getPurchaseOrders],
      delete_all_purchase_orders: ["Pedidos actualizados", getPurchaseOrders],
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

  const ensureBackendReady = async () => {
    // Evita enviar ordenes si Django/MongoDB todavia no estan disponibles.
    if (backendReady) {
      return true;
    }

    setBackendChecking(true);
    try {
      await pingBackend();
      setBackendReady(true);
      return true;
    } catch {
      setBackendReady(false);
      return false;
    } finally {
      setBackendChecking(false);
    }
  };

  const handleSubmit = async (event) => {
    // Flujo principal del chat: valida entrada, gestiona tema/confirmaciones,
    // llama al agente y actualiza mensajes + panel de resultados.
    event.preventDefault();
    if (!input.trim() || loading) {
      return;
    }

    const userMessage = input.trim();
    setMessages((current) => [...current, { role: "user", content: userMessage }]);
    setInput("");
    setLoading(true);

    try {
      const backendAvailable = await ensureBackendReady();
      if (!backendAvailable) {
        throw new Error("El backend aun se esta iniciando. Espera un momento y vuelve a intentarlo.");
      }

      const normalizedMessage = normalizeMessage(userMessage);
      const requestedTheme = detectThemeCommand(userMessage);

      if (requestedTheme) {
        // Cambio de tema local: no consume LLM ni toca datos del ERP.
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
        // Si habia una accion sensible pendiente, aqui se cancela sin llamar al backend.
        const cancelledAction = pendingAction.pending_action;
        setPendingAction(null);
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: cancellationMessages[cancelledAction] || "Operacion cancelada. No se han aplicado cambios.",
            meta: `Cancelado | ${actionLabels[cancelledAction] || "Operacion ERP"}`,
          },
        ]);
        return;
      }

      const outgoingMessage =
        // Si el usuario responde "si", se envia el token de confirmacion al backend.
        pendingAction && ["si", "s", "yes"].includes(normalizedMessage)
          ? pendingAction.confirmation_token || "confirma eliminar todo el inventario"
          : userMessage;

      const payload = provider ? { message: outgoingMessage, provider } : { message: outgoingMessage };
      const response = await postAgentMessage(payload);
      setBackendReady(true);
      const actionLabel = actionLabels[response.action] || "Operacion ERP";
      const providerDetail = response.provider_status ? ` | ${response.provider_status}` : "";

      if (response.action === "confirmation_required" && response.data?.pending_action) {
        // El backend pide confirmacion para operaciones sensibles o masivas.
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
        // Estas acciones ya devuelven datos listos para pintar; no hace falta
        // llamar otra vez a un endpoint de lista.
        show_audit_history: "Trazabilidad",
        configure_auto_replenishment: "Reposicion automatica",
      };

      if (directPanelTitles[response.action] && response.data) {
        // Algunas acciones muestran directamente los datos devueltos por el agente.
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
      setBackendReady(false);
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
    // Permite enviar con Enter y reservar Shift+Enter por si se quisiera texto largo.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  };

  return (
    <main className={`layout theme-${theme}`}>
      <section className="app-shell">
        {/* Cabecera: nombre de la app, descripcion corta y selector del proveedor LLM. */}
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
              <span>Proveedor LLM</span>
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="mock">Mock</option>
                <option value="gemini">Gemini</option>
                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                <option value="gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</option>
                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
              </select>
              <small>{providerNotes[provider]}</small>
            </label>
          </div>
        </header>

        <div className="content-grid">
          {/* Panel izquierdo: conversacion y formulario para mandar ordenes al agente. */}
          <section className="conversation-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Chat operativo</p>
                <h2>Gestiona el almacen por conversacion</h2>
              </div>
              <div className={`status-dot ${loading ? "status-busy" : ""}`}>
                {loading ? "Procesando" : backendChecking ? "Conectando" : backendReady ? "Operativo" : "Backend no listo"}
              </div>
            </div>

            <div className="messages">
              {/* Historial visual de mensajes. Cada respuesta incluye meta con accion/proveedor. */}
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
              {/* Composer: caja de texto que envia la orden al backend con Enter o boton. */}
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
              <button type="submit" disabled={loading || backendChecking}>
                {loading ? "Procesando..." : backendChecking ? "Conectando..." : "Enviar"}
              </button>
            </form>
          </section>

          {/* Panel derecho: muestra el resultado de la ultima accion o el dashboard. */}
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
