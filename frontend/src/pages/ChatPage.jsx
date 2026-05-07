import { useEffect, useMemo, useState } from "react";

import { getStatistics, postAgentMessage } from "../api/client";
import ChatMessage from "../components/ChatMessage";
import DataPanel from "../components/DataPanel";

const initialMessages = [
  {
    role: "assistant",
    content:
      "Pide una accion como 'Muestrame todos los productos' o 'Crea un pedido al proveedor ClimaSur de 10 unidades de Filtro HEPA'.",
    meta: "Proveedor inicial: mock",
  },
];

const modules = [
  { name: "Resumen", detail: "Panel ejecutivo", active: true },
  { name: "Inventario", detail: "Stock y rotacion" },
  { name: "Compras", detail: "Pedidos y proveedores" },
  { name: "Desechos", detail: "Mermas y caducidad" },
  { name: "Analitica", detail: "Indicadores ERP" },
  { name: "Automatizaciones", detail: "Flujos sugeridos" },
];

const quickActions = [
  "Consultar stock critico",
  "Registrar pedido urgente",
  "Revisar desechos por caducidad",
];

function formatCurrency(value) {
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
}

function buildMetrics(statistics) {
  if (!statistics) {
    return [
      { label: "Productos criticos", value: "--", tone: "warning" },
      { label: "Perdida por desechos", value: "--", tone: "danger" },
      { label: "Pedidos activos", value: "--", tone: "neutral" },
      { label: "Proveedores con actividad", value: "--", tone: "success" },
    ];
  }

  const lowStockCount = statistics.low_stock_products?.length || 0;
  const wasteLoss = (statistics.waste_economic_losses || []).reduce(
    (sum, item) => sum + (Number(item.economic_loss) || 0),
    0,
  );
  const orderCount = (statistics.orders_by_supplier || []).reduce(
    (sum, item) => sum + (Number(item.orders_count) || 0),
    0,
  );
  const suppliersWithOrders = statistics.orders_by_supplier?.length || 0;

  return [
    { label: "Productos criticos", value: lowStockCount, tone: "warning" },
    { label: "Perdida por desechos", value: formatCurrency(wasteLoss), tone: "danger" },
    { label: "Pedidos activos", value: orderCount, tone: "neutral" },
    { label: "Proveedores con actividad", value: suppliersWithOrders, tone: "success" },
  ];
}

export default function ChatPage() {
  const [provider, setProvider] = useState(import.meta.env.VITE_DEFAULT_LLM_PROVIDER || "mock");
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultData, setResultData] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function loadStatistics() {
      try {
        const overview = await getStatistics();
        if (mounted) {
          setStatistics(overview);
          setStatsError("");
        }
      } catch (error) {
        if (mounted) {
          setStatsError(error.message);
        }
      } finally {
        if (mounted) {
          setStatsLoading(false);
        }
      }
    }

    loadStatistics();

    return () => {
      mounted = false;
    };
  }, []);

  const metrics = useMemo(() => buildMetrics(statistics), [statistics]);
  const activeData = resultData || statistics;

  const activityFeed = useMemo(() => {
    const latestMessages = [...messages].slice(-4).reverse();

    return latestMessages.map((message, index) => ({
      id: `${message.role}-${index}`,
      title: message.role === "user" ? "Solicitud enviada" : "Respuesta del ERP",
      detail: message.content,
    }));
  }, [messages]);

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
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.reply,
          meta: `Accion: ${response.action} | Proveedor: ${response.provider}`,
        },
      ]);
      setResultData(response.data);
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

  return (
    <main className="erp-layout">
      <aside className="sidebar">
        <div className="brand-card">
          <p className="brand-kicker">Smart ERP</p>
          <h1>Centro operativo</h1>
          <p>Una consola unica para inventario, compras, desechos y analitica asistida.</p>
        </div>

        <nav className="module-nav" aria-label="Modulos ERP">
          {modules.map((module) => (
            <button
              key={module.name}
              type="button"
              className={`module-item${module.active ? " module-item-active" : ""}`}
            >
              <span>{module.name}</span>
              <small>{module.detail}</small>
            </button>
          ))}
        </nav>

        <section className="sidebar-card">
          <p className="section-label">Accesos rapidos</p>
          <div className="pill-list">
            {quickActions.map((action) => (
              <span key={action} className="info-pill">
                {action}
              </span>
            ))}
          </div>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="section-label">Dashboard ERP</p>
            <h2>Vision operativa de compras, stock y mermas</h2>
            <p className="topbar-copy">
              Una experiencia mas cercana a Odoo: paneles, estados, actividad reciente y un
              copiloto conectado a procesos reales.
            </p>
          </div>

          <div className="topbar-controls">
            <label className="provider-box">
              <span>Proveedor LLM</span>
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="mock">Mock</option>
                <option value="openai">OpenAI</option>
                <option value="gemini">Gemini</option>
                <option value="local">Local</option>
              </select>
            </label>

            <div className="status-card">
              <span className="status-dot" />
              <div>
                <strong>{statsLoading ? "Sincronizando" : "Sistema listo"}</strong>
                <p>{statsError || "Datos vivos de estadisticas y acciones del agente."}</p>
              </div>
            </div>
          </div>
        </header>

        <section className="metrics-grid">
          {metrics.map((metric) => (
            <article key={metric.label} className={`metric-card tone-${metric.tone}`}>
              <p>{metric.label}</p>
              <strong>{metric.value}</strong>
            </article>
          ))}
        </section>

        <section className="workspace-grid">
          <section className="primary-column">
            <article className="feature-card">
              <div className="feature-copy">
                <p className="section-label">Centro de control</p>
                <h3>Supervisa operaciones y ejecuta acciones desde lenguaje natural</h3>
                <p>
                  El agente puede consultar productos, crear pedidos y revisar incidencias sin salir
                  de la vista principal.
                </p>
              </div>
              <div className="feature-board">
                <div>
                  <span>Stock bajo control</span>
                  <strong>{metrics[0].value}</strong>
                </div>
                <div>
                  <span>Pedidos registrados</span>
                  <strong>{metrics[2].value}</strong>
                </div>
                <div>
                  <span>Alertas de desperdicio</span>
                  <strong>{statistics?.most_wasted_products?.length || 0}</strong>
                </div>
              </div>
            </article>

            <section className="conversation-panel">
              <div className="panel-heading">
                <div>
                  <p className="section-label">Copiloto ERP</p>
                  <h3>Asistente operativo</h3>
                </div>
                <span className="panel-badge">{loading ? "Procesando" : "Disponible"}</span>
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
                  rows="3"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ejemplo: registra un desecho de 3 unidades de Filtro HEPA por caducidad"
                />
                <button type="submit" disabled={loading}>
                  {loading ? "Procesando..." : "Enviar instruccion"}
                </button>
              </form>
            </section>
          </section>

          <aside className="secondary-column">
            <section className="sidebar-card activity-card">
              <div className="panel-heading">
                <div>
                  <p className="section-label">Actividad</p>
                  <h3>Ultimos eventos</h3>
                </div>
              </div>

              <div className="activity-list">
                {activityFeed.map((item) => (
                  <article key={item.id} className="activity-item">
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                  </article>
                ))}
              </div>
            </section>

            <section className="sidebar-card insights-card">
              <div className="panel-heading">
                <div>
                  <p className="section-label">Analitica</p>
                  <h3>Datos del sistema</h3>
                </div>
                <span className="panel-badge subtle">
                  {resultData ? "Resultado actual" : "Vista general"}
                </span>
              </div>
              <DataPanel data={activeData} />
            </section>
          </aside>
        </section>
      </section>
    </main>
  );
}
