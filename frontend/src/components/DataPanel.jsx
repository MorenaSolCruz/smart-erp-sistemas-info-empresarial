function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return value ?? "";
  }
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(number);
}

function SimpleBarChart({ title, rows, labelKey, valueKey }) {
  if (!rows?.length) {
    return (
      <section className="panel-card">
        <h3>{title}</h3>
        <p>Sin datos todavía.</p>
      </section>
    );
  }

  const maxValue = Math.max(...rows.map((row) => Number(row[valueKey]) || 0), 1);

  return (
    <section className="panel-card">
      <h3>{title}</h3>
      <div className="chart-list">
        {rows.map((row, index) => (
          <div className="chart-row" key={`${row[labelKey]}-${index}`}>
            <div className="chart-label">{row[labelKey]}</div>
            <div className="chart-bar-track">
              <div
                className="chart-bar-fill"
                style={{ width: `${(Number(row[valueKey]) / maxValue) * 100}%` }}
              />
            </div>
            <div className="chart-value">{formatNumber(row[valueKey])}</div>
          </div>
        ))}
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
        <SimpleBarChart
          title="Productos más desechados"
          rows={data.most_wasted_products}
          labelKey="product_name"
          valueKey="wasted_quantity"
        />
        <SimpleBarChart
          title="Pérdidas económicas por motivo"
          rows={data.waste_economic_losses}
          labelKey="reason"
          valueKey="economic_loss"
        />
      </div>

      <div className="panel-grid">
        <DataTable title="Productos con menor stock" rows={data.low_stock_products} />
        <DataTable title="Pedidos por proveedor" rows={data.orders_by_supplier} />
      </div>
    </div>
  );
}

export default function DataPanel({ data }) {
  if (!data) {
    return (
      <section className="panel-card empty-state">
        <h3>Resultados</h3>
        <p>Sin respuesta estructurada todavía.</p>
      </section>
    );
  }

  if (Array.isArray(data)) {
    return <DataTable title="Resultado" rows={data} />;
  }

  if (!data.low_stock_products && !data.most_wasted_products) {
    return <DataTable title="Resultado" rows={[data]} />;
  }

  return <StatisticsDashboard data={data} />;
}
