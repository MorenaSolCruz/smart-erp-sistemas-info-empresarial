import { useState } from "react";

import { postAgentMessage } from "../api/client";
import ChatMessage from "../components/ChatMessage";
import DataPanel from "../components/DataPanel";

const initialMessages = [
  {
    role: "assistant",
    content: "Escribe una instrucción como 'Muéstrame todos los productos' o 'Crea un pedido al proveedor ClimaSur de 10 unidades de Filtro HEPA'.",
    meta: "Proveedor inicial: mock",
  },
];

export default function ChatPage() {
  const [provider, setProvider] = useState(import.meta.env.VITE_DEFAULT_LLM_PROVIDER || "mock");
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultData, setResultData] = useState(null);

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
          meta: `Acción: ${response.action} | Proveedor: ${response.provider}`,
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

  return (
    <main className="layout">
      <section className="chat-shell">
        <div className="hero">
          <div>
            <p className="eyebrow">ERP Conversacional</p>
            <h1>Gestión empresarial desde lenguaje natural</h1>
            <p className="hero-copy">
              Este prototipo conecta un chat con operaciones ERP sobre productos, proveedores, pedidos,
              desechos y estadísticas.
            </p>
          </div>

          <label className="provider-box">
            <span>Proveedor LLM</span>
            <select value={provider} onChange={(event) => setProvider(event.target.value)}>
              <option value="mock">Mock</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Gemini</option>
              <option value="local">Local</option>
            </select>
          </label>
        </div>

        <div className="content-grid">
          <section className="conversation-panel">
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
                placeholder="Ejemplo: Registra un desecho de 3 unidades de Filtro HEPA por caducidad"
              />
              <button type="submit" disabled={loading}>
                {loading ? "Procesando..." : "Enviar"}
              </button>
            </form>
          </section>

          <aside className="data-panel">
            <DataPanel data={resultData} />
          </aside>
        </div>
      </section>
    </main>
  );
}

