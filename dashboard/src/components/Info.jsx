/** Botón «?» que muestra una explicación al pasar el mouse o al enfocarlo con el teclado. */
export default function Info({ children, label = "¿Qué mide?" }) {
  return (
    <span className="info">
      <button type="button" className="info-btn" aria-label={label}>?</button>
      <span role="tooltip" className="info-pop">{children}</span>
    </span>
  );
}
