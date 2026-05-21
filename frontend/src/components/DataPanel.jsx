function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return value ?? "";
  }
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(number);
}

const chartColors = ["#37d7ff", "#55efc4", "#a78bfa", "#ff7ac8", "#fbbf24", "#fb7185"];

function chartPercent(value, total) {
  return formatNumber((Number(value || 0) / (total || 1)) * 100);
}

function DonutChart({ title, rows, labelKey, valueKey }) {
  if (!rows?.length) {
    return (
      <section className="panel-card">
        <h3>{title}</h3>
        <p>Sin datos todavía.</p>
      </section>
    );
  }

  const totalValue = rows.reduce((total, row) => total + Number(row[valueKey] || 0), 0) || 1;
  const radius = 43;
  const circumference = 2 * Math.PI * radius;
  let currentOffset = 0;

  return (
    <section className="panel-card chart-card donut-card">
      <h3>{title}</h3>
      <div className="donut-layout">
        <div className="donut-figure" aria-label={title}>
          <svg viewBox="0 0 120 120" role="img">
            <circle className="donut-track" cx="60" cy="60" r={radius} />
            {rows.map((row, index) => {
              const value = Number(row[valueKey]) || 0;
              const arc = (value / totalValue) * circumference;
              const dashOffset = currentOffset;
              currentOffset += arc;
              return (
                <circle
                  className="donut-segment"
                  key={`${row[labelKey]}-${index}`}
                  cx="60"
                  cy="60"
                  r={radius}
                  stroke={chartColors[index % chartColors.length]}
                  strokeDasharray={`${arc} ${circumference - arc}`}
                  strokeDashoffset={-dashOffset}
                >
                  <title>{`${row[labelKey]}: ${formatNumber(value)} (${chartPercent(value, totalValue)}%)`}</title>
                </circle>
              );
            })}
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
                <small>
                  {chartPercent(row[valueKey], totalValue)}% del total
                </small>
              </div>
              <span className="legend-value">{formatNumber(row[valueKey])}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ColumnChart({ title, rows, labelKey, valueKey }) {
  if (!rows?.length) {
    return (
      <section className="panel-card">
        <h3>{title}</h3>
        <p>Sin datos todavía.</p>
      </section>
    );
  }

  const maxValue = Math.max(...rows.map((row) => Number(row[valueKey]) || 0), 1);
  const totalValue = rows.reduce((total, row) => total + Number(row[valueKey] || 0), 0) || 1;

  return (
    <section className="panel-card chart-card column-card">
      <h3>{title}</h3>
      <div className="column-chart" aria-label={title}>
        {rows.map((row, index) => {
          const value = Number(row[valueKey]) || 0;
          const height = Math.max((value / maxValue) * 100, 8);
          return (
            <div
              className="column-item"
              key={`${row[labelKey]}-${index}`}
              data-tooltip={`${row[labelKey]}: ${formatNumber(value)} (${chartPercent(value, totalValue)}%)`}
            >
              <strong>{formatNumber(value)}</strong>
              <div className="column-track">
                <div
                  className="column-fill"
                  style={{
                    height: `${height}%`,
                    background: `linear-gradient(180deg, ${chartColors[(index + 2) % chartColors.length]}, ${chartColors[(index + 3) % chartColors.length]})`,
                  }}
                />
              </div>
              <span>{row[labelKey]}</span>
              <small>{chartPercent(value, totalValue)}%</small>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function DataTable({ title, rows }) {
  if (!rows?.length) {
    return (
      <section className="panel-card">
        <h3>{title}</h3>
        <p>Sin datos todavía.</p>
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
    reason: "Motivo",
    date: "Fecha",
    economic_loss: "Perdida economica",
    orders_count: "Pedidos",
    wasted_quantity: "Unidades desechadas",
  };
  const formatValue = (value) => {
    if (Array.isArray(value)) {
      return value.map((item) => (typeof item === "object" ? JSON.stringify(item) : item)).join(" | ");
    }
    if (value && typeof value === "object") {
      return JSON.stringify(value);
    }
    if (typeof value === "number") {
      return formatNumber(value);
    }
    return String(value ?? "");
  };

  return (
    <section className="panel-card">
      <h3>{title}</h3>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{columnLabels[column] || column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{formatValue(row[column])}</td>
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
    </section>
  );
}

function StatisticsDashboard({ data }) {
  const productsCount = data.low_stock_products?.length || 0;
  const wastedUnits = (data.most_wasted_products || []).reduce(
    (total, row) => total + Number(row.wasted_quantity || 0),
    0,
  );
  const economicLoss = (data.waste_economic_losses || []).reduce(
    (total, row) => total + Number(row.economic_loss || 0),
    0,
  );
  const ordersCount = (data.orders_by_supplier || []).reduce(
    (total, row) => total + Number(row.orders_count || 0),
    0,
  );

  return (
    <div className="stats-dashboard">
      <div className="kpi-grid">
        <KpiCard label="Productos monitorizados" value={productsCount} tone="info" />
        <KpiCard label="Unidades desechadas" value={wastedUnits} tone="warning" />
        <KpiCard label="Pérdida económica" value={economicLoss} tone="danger" />
        <KpiCard label="Pedidos registrados" value={ordersCount} tone="success" />
      </div>

      <div className="stats-charts">
        <DonutChart
          title="Distribución de productos desechados"
          rows={data.most_wasted_products}
          labelKey="product_name"
          valueKey="wasted_quantity"
        />
        <ColumnChart
          title="Pérdidas económicas por motivo"
          rows={data.waste_economic_losses}
          labelKey="reason"
          valueKey="economic_loss"
        />
      </div>
    </div>
  );
}

export default function DataPanel({ data, title = "Resultados", isRefreshing = false }) {
  if (!data) {
    return (
      <section className="panel-card empty-state">
        <h3>{title}</h3>
        <p>Maja mostrará aquí los datos actualizados tras cada orden.</p>
      </section>
    );
  }

  if (Array.isArray(data)) {
    const isProductList = data.every((row) => "name" in row && "stock" in row && "unit_price" in row);
    return (
      <div className={isRefreshing ? "panel-refreshing" : ""}>
        {isProductList ? <ProductLivePanel title={title} rows={data} /> : <DataTable title={title} rows={data} />}
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
                <div
                  className="inventory-fill"
                  style={{ width: `${Math.max((Number(product.stock) / maxStock) * 100, 3)}%` }}
                />
              </div>
              <div className="inventory-meta">
                <span>Precio {formatNumber(product.unit_price)} €</span>
                <span>Mínimo {formatNumber(product.minimum_stock)}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
