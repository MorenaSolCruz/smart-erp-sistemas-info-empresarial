function formatLabel(label) {
  return label
    .split("_")
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}

function SimpleBarChart({ title, rows, labelKey, valueKey }) {
  if (!rows?.length) {
    return (
      <section className="panel-card compact-card">
        <h3>{title}</h3>
        <p>Sin datos todavia.</p>
      </section>
    );
  }

  const maxValue = Math.max(...rows.map((row) => Number(row[valueKey]) || 0), 1);

  return (
    <section className="panel-card compact-card">
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
            <div className="chart-value">{row[valueKey]}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function DataTable({ title, rows }) {
  if (!rows?.length) {
    return (
      <section className="panel-card compact-card">
        <h3>{title}</h3>
        <p>Sin datos todavia.</p>
      </section>
    );
  }

  const columns = Object.keys(rows[0]);

  return (
    <section className="panel-card compact-card">
      <h3>{title}</h3>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{formatLabel(column)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{String(row[column] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SummaryCards({ data }) {
  const lowStock = data.low_stock_products?.length || 0;
  const wasteAlerts = data.most_wasted_products?.length || 0;
  const supplierLoad = data.orders_by_supplier?.length || 0;

  const totalLoss = (data.waste_economic_losses || []).reduce(
    (sum, item) => sum + (Number(item.economic_loss) || 0),
    0,
  );

  const cards = [
    { label: "Stock critico", value: lowStock },
    { label: "Productos con merma", value: wasteAlerts },
    { label: "Proveedores activos", value: supplierLoad },
    { label: "Perdida estimada", value: `${Math.round(totalLoss)} EUR` },
  ];

  return (
    <div className="summary-grid">
      {cards.map((card) => (
        <article key={card.label} className="summary-card">
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </article>
      ))}
    </div>
  );
}

export default function DataPanel({ data }) {
  if (!data) {
    return (
      <section className="panel-card compact-card">
        <h3>Resultados</h3>
        <p>Las tablas y graficos apareceran aqui cuando el sistema devuelva datos.</p>
      </section>
    );
  }

  if (Array.isArray(data)) {
    return <DataTable title="Resultado" rows={data} />;
  }

  if (!data.low_stock_products && !data.most_wasted_products) {
    return <DataTable title="Resultado" rows={[data]} />;
  }

  return (
    <div className="panel-grid">
      <SummaryCards data={data} />
      <DataTable title="Productos con menor stock" rows={data.low_stock_products} />
      <SimpleBarChart
        title="Productos mas desechados"
        rows={data.most_wasted_products}
        labelKey="product_name"
        valueKey="wasted_quantity"
      />
      <SimpleBarChart
        title="Perdidas economicas por desecho"
        rows={data.waste_economic_losses}
        labelKey="reason"
        valueKey="economic_loss"
      />
      <DataTable title="Pedidos por proveedor" rows={data.orders_by_supplier} />
    </div>
  );
}
