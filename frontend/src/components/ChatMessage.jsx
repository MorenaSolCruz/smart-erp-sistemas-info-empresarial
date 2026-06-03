export default function ChatMessage({ role, content, meta, thinking = false }) {
  // Renderiza cada burbuja del chat: mensajes del usuario, respuestas de Maja
  // y el estado animado mientras el backend procesa la orden.
  return (
    <div className={`message message-${role} ${thinking ? "message-thinking" : ""}`}>
      <div className="message-role">{role === "user" ? "Usuario" : "Maja"}</div>
      <div className="message-content">
        {thinking ? (
          <span className="typing-dots" aria-label="Maja está pensando">
            <span />
            <span />
            <span />
          </span>
        ) : (
          content
        )}
      </div>
      {meta ? <div className="message-meta">{meta}</div> : null}
    </div>
  );
}

