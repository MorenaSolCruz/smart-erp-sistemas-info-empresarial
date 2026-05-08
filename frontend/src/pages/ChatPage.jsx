import { useState } from "react";

import { postAgentMessage } from "../api/client";
import ChatMessage from "../components/ChatMessage";
import DataPanel from "../components/DataPanel";

const initialMessages = [
  {
    role: "assistant",
    content: "Consola lista. Indica la operación ERP que necesitas realizar.",
    meta: "Entrada por lenguaje natural | Entorno local",
  },
];

const actionLabels = {
  list_products: "Consulta de productos",
  create_product: "Alta de producto",
  update_product: "Actualización de producto",
  delete_product: "Baja de producto",
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
  mock: "Parser local de pruebas.",
  openai: "OpenAI API. Requiere OPENAI_API_KEY.",
  gemini: "Gemini API. Requiere GEMINI_API_KEY.",
  claude: "Claude API. Requiere ANTHROPIC_API_KEY.",
  local: "Simulado hasta configurar LOCAL_LLM_URL.",
};

export default function ChatPage() {
  const [provider, setProvider] = useState(import.meta.env.VITE_DEFAULT_LLM_PROVIDER || "mock");
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultData, setResultData] = useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem("erp-theme") || "light");

  const toggleTheme = () => {
    setTheme((currentTheme) => {
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      localStorage.setItem("erp-theme", nextTheme);
      return nextTheme;
    });
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
      const response = await postAgentMessage({ message: userMessage, provider });
      const actionLabel = actionLabels[response.action] || "Operación ERP";
      const providerDetail = response.provider_status ? ` | ${response.provider_status}` : "";
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.reply,
          meta: `${response.success ? "Completado" : "Revisar"} | ${actionLabel} | Proveedor ${response.provider}${providerDetail}`,
        },
      ]);
      setResultData(response.data);
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
          <div>
            <p className="eyebrow">ERP Conversacional</p>
            <h1>Consola de operaciones</h1>
          </div>

          <div className="system-strip" aria-label="Estado del sistema">
            <span>API local</span>
            <span>MongoDB</span>
            <span>CRUD por LLM</span>
          </div>

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
              <span>Proveedor LLM</span>
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="mock">Mock</option>
                <option value="openai">OpenAI</option>
                <option value="gemini">Gemini</option>
                <option value="claude">Claude</option>
                <option value="local">Local simulado</option>
              </select>
              <small>{providerNotes[provider]}</small>
            </label>
          </div>
        </header>

        <div className="content-grid">
          <section className="conversation-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Entrada única</p>
                <h2>Chat ERP</h2>
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
            </div>

            <form className="composer" onSubmit={handleSubmit}>
              <textarea
                rows="2"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="Ejemplo: crea un producto llamado Filtro HEPA con stock 20 y precio 35"
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
                <h2>Datos devueltos</h2>
              </div>
            </div>
            <DataPanel data={resultData} />
          </aside>
        </div>
      </section>
    </main>
  );
}

