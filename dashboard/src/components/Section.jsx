import Info from "./Info.jsx";

/** Bloque de página con título, descripción y un elemento opcional a la derecha. */
export function Section({ title, desc, aside, children }) {
  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {desc && <p>{desc}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** Tarjeta con título, descripción y explicación «?» opcional. */
export function Card({ title, desc, info, action, children, className = "" }) {
  return (
    <div className={`card ${className}`}>
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {desc && <p>{desc}</p>}
        </div>
        {action}
        {info && <Info>{info}</Info>}
      </div>
      {children}
    </div>
  );
}
