export default function ChatMessage({ role, content, meta }) {
  return (
    <div className={`message message-${role}`}>
      <div className="message-role">{role === "user" ? "Usuario" : "ERP"}</div>
      <div className="message-content">{content}</div>
      {meta ? <div className="message-meta">{meta}</div> : null}
    </div>
  );
}

