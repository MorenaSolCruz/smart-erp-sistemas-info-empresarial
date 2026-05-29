function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return value ?? "";
  }
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(number);
}

function formatDate(value) {
  if (!value) {
    return "Sin fecha";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

const chartColors = ["#37d7ff", "#55efc4", "#a78bfa", "#ff7ac8", "#fbbf24", "#fb7185"];

function chartPercent(value, total) {
  return formatNumber((Number(value || 0) / (total || 1)) * 100);
}

function polarToCartesian(centerX, centerY, radius, angleInDegrees) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  };
}

function describeArc(x, y, radius, startAngle, endAngle) {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return ["M", start.x, start.y, "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y].join(" ");
}

function shortLabel(value, maxLength = 14) {
  const label = String(value ?? "");
  return label.length > maxLength ? `${label.slice(0, maxLength - 1)}...` : label;
}

function chartPoint(x, y) {
  return `${Number(x).toFixed(2)},${Number(y).toFixed(2)}`;
}

function statusTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (["received", "success", "active"].includes(normalized)) {
    return "success";
  }
  if (["pending", "partially_received"].includes(normalized)) {
    return "warning";
  }
  if (["cancelled", "closed_partial"].includes(normalized)) {
    return "danger";
  }
  return "neutral";
}

function StatusBadge({ value }) {
  return <span className={`status-badge status-${statusTone(value)}`}>{String(value ?? "-")}</span>;
}

function InlineMetric({ label, value }) {
  return (
    <span className="inline-metric">
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function renderCellContent(column, value) {
  if (column === "status") {
    return <StatusBadge value={value} />;
  }

  if (["created_at", "updated_at", "received_at", "cancelled_at", "date", "timestamp"].includes(column)) {
    return <span className="muted-cell">{formatDate(value)}</span>;
  }

  if (column === "items" && Array.isArray(value)) {
    return (
      <div className="stack-cell">
        {value.map((item, index) => (
          <article className="mini-card" key={`${item.product_id || item.product_name}-${index}`}>
            <div className="mini-card-head">
              <strong>{item.product_name || "Producto"}</strong>
              <StatusBadge value={item.line_status || item.status || "pending"} />
            </div>
            <div className="mini-metrics">
              <InlineMetric label="Pedidas" value={formatNumber(item.quantity)} />
              <InlineMetric label="Pendientes" value={formatNumber(item.pending_quantity)} />
              <InlineMetric label="Recibidas" value={formatNumber(item.received_quantity)} />
              <InlineMetric label="Importe" value={formatNumber(item.line_total ?? item.unit_price)} />
            </div>
          </article>
        ))}
      </div>
    );
  }

  if (column === "history" && Array.isArray(value)) {
    return (
      <div className="stack-cell history-cell">
        {value.map((entry, index) => (
          <article className="history-entry" key={`${entry.timestamp || entry.event}-${index}`}>
            <div className="mini-card-head">
              <strong>{entry.summary || entry.event || "Evento"}</strong>
              <span className="muted-cell">{formatDate(entry.timestamp)}</span>
            </div>
            {entry.items?.length ? (
              <div className="pill-row">
                {entry.items.map((item, itemIndex) => (
                  <span className="info-pill" key={`${item.product_name || item.quantity}-${itemIndex}`}>
                    {(item.product_name || "Linea") + ": " + formatNumber(item.quantity || item.received_quantity || 0)}
                  </span>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    );
  }

  if (Array.isArray(value)) {
    return (
      <div className="pill-row">
        {value.map((item, index) => (
          <span className="info-pill" key={`${String(item)}-${index}`}>
            {typeof item === "object" ? JSON.stringify(item) : String(item)}
          </span>
        ))}
      </div>
    );
  }

  if (value && typeof value === "object") {
    return (
      <div className="stack-cell">
        {Object.entries(value).map(([key, nestedValue]) => (
          <div className="inline-pair" key={key}>
            <span>{key}</span>
            <strong>{typeof nestedValue === "number" ? formatNumber(nestedValue) : String(nestedValue ?? "-")}</strong>
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === "number") {
    return formatNumber(value);
  }

  return String(value ?? "");
}

function DonutChart({ title, rows, labelKey, valueKey }) {
  if (!rows?.length) {
    return (
      <section className="panel-card">
        <h3>{title}</h3>
        <p>Sin datos todavia.</p>
      </section>
    );
  }

  const totalValue = rows.reduce((total, row) => total + Number(row[valueKey] || 0), 0) || 1;
  let currentAngle = 0;

  return (
    <section className="panel-card chart-card donut-card advanced-chart">
      <div className="chart-card-head">
        <div>
          <h3>{title}</h3>
          <p>Participacion por producto</p>
        </div>
        <span>{formatNumber(totalValue)} uds.</span>
      </div>
      <div className="donut-layout">
        <div className="donut-figure" aria-label={title}>
          <svg viewBox="0 0 190 190" role="img">
            <defs>
              <filter id="donutGlow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <circle className="donut-track" cx="95" cy="95" r="62" />
            {rows.map((row, index) => {
              const value = Number(row[valueKey]) || 0;
              const sweep = (value / totalValue) * 359.5;
              const startAngle = currentAngle;
              const endAngle = currentAngle + sweep;
              currentAngle = endAngle;
              return (
                <path
                  className="donut-segment"
                  key={`${row[labelKey]}-${index}`}
                  d={describeArc(95, 95, 62, startAngle, endAngle)}
                  stroke={chartColors[index % chartColors.length]}
                  filter="url(#donutGlow)"
                >
                  <title>{`${row[labelKey]}: ${formatNumber(value)} (${chartPercent(value, totalValue)}%)`}</title>
                </path>
              );
            })}
            <circle className="donut-inner-ring" cx="95" cy="95" r="41" />
          </svg>
          <div className="donut-center">
            <strong>{formatNumber(totalValue)}</strong>
            <span>Total</span>
          </div>
        </div>

        <div className="chart-legend">
          {rows.map((row, index) => (
            <div
              className="legend-item"
              key={`${row[labelKey]}-legend-${index}`}
              data-tooltip={`${row[labelKey]}: ${formatNumber(row[valueKey])} (${chartPercent(row[valueKey], totalValue)}%)`}
            >
              <span className="legend-dot" style={{ backgroundColor: chartColors[index % chartColors.length] }} />
              <div>
                <strong>{row[labelKey]}</strong>
                <small>{chartPercent(row[valueKey], totalValue)}% del total</small>
              </div>
              <span className="legend-value">{formatNumber(row[valueKey])}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ParetoChart({ title, rows, labelKey, valueKey }) {
  if (!rows?.length) {
    return (
      <section className="panel-card">
        <h3>{title}</h3>
        <p>Sin datos todavia.</p>
      </section>
    );
  }

  const sortedRows = [...rows].sort((a, b) => Number(b[valueKey] || 0) - Number(a[valueKey] || 0));
  const maxValue = Math.max(...sortedRows.map((row) => Number(row[valueKey]) || 0), 1);
  const totalValue = sortedRows.reduce((total, row) => total + Number(row[valueKey] || 0), 0) || 1;
  const chartWidth = 360;
  const chartHeight = 230;
  const left = 44;
  const right = 36;
  const top = 24;
  const bottom = 48;
  const plotWidth = chartWidth - left - right;
  const plotHeight = chartHeight - top - bottom;
  const slotWidth = plotWidth / sortedRows.length;
  const barWidth = Math.min(34, slotWidth * 0.48);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  let runningTotal = 0;
  const linePoints = sortedRows.map((row, index) => {
    runningTotal += Number(row[valueKey]) || 0;
    const x = left + index * slotWidth + slotWidth / 2;
    const y = top + plotHeight - (runningTotal / totalValue) * plotHeight;
    return { x, y, percent: (runningTotal / totalValue) * 100 };
  });
  const areaPath = linePoints.length
    ? `M ${chartPoint(linePoints[0].x, top + plotHeight)} L ${linePoints.map((point) => chartPoint(point.x, point.y)).join(" L ")} L ${chartPoint(linePoints[linePoints.length - 1].x, top + plotHeight)} Z`
    : "";
  const linePath = linePoints.length ? `M ${linePoints.map((point) => chartPoint(point.x, point.y)).join(" L ")}` : "";

  return (
    <section className="panel-card chart-card pareto-card advanced-chart">
      <div className="chart-card-head">
        <div>
          <h3>{title}</h3>
          <p>Barras de impacto y linea acumulada</p>
        </div>
        <span>{formatNumber(totalValue)} total</span>
      </div>
      <div className="svg-chart-wrap">
        <svg className="pareto-svg" viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label={title}>
          <defs>
            <linearGradient id="paretoArea" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#37d7ff" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#37d7ff" stopOpacity="0.02" />
            </linearGradient>
            <linearGradient id="paretoBar" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#ff7ac8" />
              <stop offset="100%" stopColor="#a78bfa" />
            </linearGradient>
          </defs>
          {ticks.map((tick) => {
            const y = top + plotHeight - tick * plotHeight;
            return (
              <g key={`pareto-tick-${tick}`}>
                <line className="axis-grid" x1={left} x2={chartWidth - right} y1={y} y2={y} />
                <text className="axis-label" x={left - 10} y={y + 4} textAnchor="end">
                  {formatNumber(maxValue * tick)}
                </text>
                <text className="axis-label" x={chartWidth - right + 8} y={y + 4}>
                  {Math.round(tick * 100)}%
                </text>
              </g>
            );
          })}
          <line className="axis-line" x1={left} x2={left} y1={top} y2={chartHeight - bottom} />
          <line className="axis-line" x1={chartWidth - right} x2={chartWidth - right} y1={top} y2={chartHeight - bottom} />
          <line className="axis-line" x1={left} x2={chartWidth - right} y1={chartHeight - bottom} y2={chartHeight - bottom} />
          {sortedRows.map((row, index) => {
            const value = Number(row[valueKey]) || 0;
            const height = Math.max((value / maxValue) * plotHeight, 8);
            const x = left + index * slotWidth + (slotWidth - barWidth) / 2;
            const y = top + plotHeight - height;
            return (
              <g className="bar-group" key={`${row[labelKey]}-${index}`}>
                <rect className="bar-hit" x={x - 8} y={top} width={barWidth + 16} height={plotHeight} rx="12">
                  <title>{`${row[labelKey]}: ${formatNumber(value)} (${chartPercent(value, totalValue)}%)`}</title>
                </rect>
                <rect className="bar-column" x={x} y={y} width={barWidth} height={height} rx="11" fill="url(#paretoBar)" />
                <text className="bar-value" x={x + barWidth / 2} y={y - 8} textAnchor="middle">
                  {formatNumber(value)}
                </text>
                <text className="bar-label" x={x + barWidth / 2} y={chartHeight - 22} textAnchor="middle">
                  {shortLabel(row[labelKey], 10)}
                </text>
                <text className="bar-percent" x={x + barWidth / 2} y={chartHeight - 8} textAnchor="middle">
                  {chartPercent(value, totalValue)}%
                </text>
              </g>
            );
          })}
          <path className="pareto-area" d={areaPath} />
          <path className="pareto-line" d={linePath} />
          {linePoints.map((point, index) => (
            <g className="pareto-point" key={`pareto-point-${index}`}>
              <circle cx={point.x} cy={point.y} r="4.5">
                <title>{`Acumulado: ${formatNumber(point.percent)}%`}</title>
              </circle>
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
}

function DataTable({ title, rows }) {
  if (!rows?.length) {
    return (
      <section className="panel-card">
        <h3>{title}</h3>
        <p>Sin datos todavia.</p>
      </section>
    );
  }

  const columns = Object.keys(rows[0]);
  const columnLabels = {
    id: "ID",
    name: "Nombre",
    description: "Descripcion",
    category: "Categoria",
    stock: "Stock",
    minimum_stock: "Stock minimo",
    unit_price: "Precio unitario",
    expiration_date: "Caducidad",
    created_at: "Creado",
    updated_at: "Actualizado",
    contact_email: "Email",
    phone: "Telefono",
    address: "Direccion",
    products_supplied: "Productos",
    supplier_id: "ID proveedor",
    supplier_name: "Proveedor",
    product_id: "ID producto",
    product_name: "Producto",
    items: "Lineas",
    quantity: "Cantidad",
    total_amount: "Importe total",
    status: "Estado",
    history: "Historial",
    reason: "Motivo",
    date: "Fecha",
    economic_loss: "Perdida economica",
    orders_count: "Pedidos",
    wasted_quantity: "Unidades desechadas",
    expired_products_count: "Productos caducados",
    expired_units: "Unidades caducadas",
    expired_economic_loss: "Perdida por caducidad",
    timestamp: "Fecha",
    action_label: "Accion",
    entity_type: "Tipo de entidad",
    entity_name: "Entidad",
    summary: "Resumen",
    enabled: "Activo",
  };

  return (
    <section className="panel-card">
      <h3>{title}</h3>
      <div className="table-wrapper">
        <table className="smart-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{columnLabels[column] || column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id || `${title}-${index}`}>
                {columns.map((column) => (
                  <td key={column} className={`col-${column}`}>
                    {renderCellContent(column, row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function KpiCard({ label, value, tone = "neutral" }) {
  return (
    <section className={`kpi-card kpi-${tone}`}>
      <span>{label}</span>
      <strong>{formatNumber(value)}</strong>
      <i aria-hidden="true" />
    </section>
  );
}

function StatisticsDashboard({ data }) {
  const productsCount = data.low_stock_products?.length || 0;
  const wastedUnits = (data.most_wasted_products || []).reduce((total, row) => total + Number(row.wasted_quantity || 0), 0);
  const economicLoss = (data.waste_economic_losses || []).reduce((total, row) => total + Number(row.economic_loss || 0), 0);
  const ordersCount = (data.orders_by_supplier || []).reduce((total, row) => total + Number(row.orders_count || 0), 0);
  const topWaste = (data.most_wasted_products || [])[0];
  const topLoss = [...(data.waste_economic_losses || [])].sort((a, b) => Number(b.economic_loss || 0) - Number(a.economic_loss || 0))[0];
  const averageLoss = wastedUnits ? economicLoss / wastedUnits : 0;

  return (
    <div className="stats-dashboard">
      <section className="panel-card executive-summary">
        <div>
          <span>Principal foco de merma</span>
          <strong>{topWaste?.product_name || "Sin datos"}</strong>
          <small>{topWaste ? `${formatNumber(topWaste.wasted_quantity)} unidades registradas` : "Aun no hay desechos registrados"}</small>
        </div>
        <div>
          <span>Motivo de mayor impacto</span>
          <strong>{topLoss?.reason || "Sin datos"}</strong>
          <small>{topLoss ? `${formatNumber(topLoss.economic_loss)} de perdida economica` : "Sin perdidas calculadas"}</small>
        </div>
        <div>
          <span>Coste medio por unidad</span>
          <strong>{formatNumber(averageLoss)}</strong>
          <small>Perdida economica / unidades desechadas</small>
        </div>
      </section>

      <div className="kpi-grid">
        <KpiCard label="Productos monitorizados" value={productsCount} tone="info" />
        <KpiCard label="Unidades desechadas" value={wastedUnits} tone="warning" />
        <KpiCard label="Perdida economica" value={economicLoss} tone="danger" />
        <KpiCard label="Pedidos registrados" value={ordersCount} tone="success" />
      </div>

      <div className="stats-charts">
        <DonutChart title="Distribucion de productos desechados" rows={data.most_wasted_products} labelKey="product_name" valueKey="wasted_quantity" />
        <ParetoChart title="Analisis Pareto de perdidas" rows={data.waste_economic_losses} labelKey="reason" valueKey="economic_loss" />
      </div>
    </div>
  );
}

function ProductLivePanel({ title, rows }) {
  const totalUnits = rows.reduce((total, product) => total + Number(product.stock || 0), 0);
  const maxStock = Math.max(...rows.map((product) => Number(product.stock) || 0), 1);

  return (
    <div className="live-panel">
      <section className="live-summary">
        <div>
          <span>Productos</span>
          <strong>{formatNumber(rows.length)}</strong>
        </div>
        <div>
          <span>Unidades</span>
          <strong>{formatNumber(totalUnits)}</strong>
        </div>
      </section>

      <section className="panel-card live-inventory">
        <h3>{title}</h3>
        <div className="inventory-list">
          {rows.map((product) => (
            <article className="inventory-row" key={product.id || product.name}>
              <div className="inventory-row-head">
                <span>{product.name}</span>
                <strong>{formatNumber(product.stock)}</strong>
              </div>
              <div className="inventory-track">
                <div className="inventory-fill" style={{ width: `${Math.max((Number(product.stock) / maxStock) * 100, 3)}%` }} />
              </div>
              <div className="inventory-meta">
                <span>Precio {formatNumber(product.unit_price)} EUR</span>
                <span>Minimo {formatNumber(product.minimum_stock)}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export default function DataPanel({ data, title = "Resultados", isRefreshing = false }) {
  if (!data) {
    return (
      <section className="panel-card empty-state">
        <h3>{title}</h3>
        <p>Maja mostrara aqui los datos actualizados tras cada orden.</p>
      </section>
    );
  }

  if (Array.isArray(data)) {
    const isProductList = data.every((row) => "name" in row && "stock" in row && "unit_price" in row);
    return <div className={isRefreshing ? "panel-refreshing" : ""}>{isProductList ? <ProductLivePanel title={title} rows={data} /> : <DataTable title={title} rows={data} />}</div>;
  }

  if (data.chart_type === "inventory_stock" && Array.isArray(data.rows)) {
    return (
      <div className={isRefreshing ? "panel-refreshing" : ""}>
        <ProductLivePanel title={data.title || title} rows={data.rows} />
      </div>
    );
  }

  if (!data.low_stock_products && !data.most_wasted_products) {
    return <DataTable title={title} rows={[data]} />;
  }

  return (
    <div className={isRefreshing ? "panel-refreshing" : ""}>
      <StatisticsDashboard data={data} />
    </div>
  );
}
