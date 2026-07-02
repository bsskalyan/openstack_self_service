import React, { useEffect, useMemo, useState } from "react";

import { api } from "./api";

const tabs = [
  { id: "dashboard", label: "Dashboard" },
  { id: "catalog", label: "Service Catalog" },
  { id: "servers", label: "Servers" },
  { id: "create", label: "Create VM" },
  { id: "images", label: "Images" },
  { id: "flavors", label: "Flavors" },
  { id: "networks", label: "Networks" },
  { id: "floatingIps", label: "Floating IPs" },
];

const emptyCreateForm = {
  name: "",
  image_id: "",
  flavor_id: "",
  network_id: "",
  key_name: "",
  security_group_id: "",
  cpu: "",
  ram_gb: "",
  disk_gb: "",
  environment: "dev",
  app_tag: "",
  cost_center: "",
  lifetime_days: "30",
  packages: "",
  public_ip_required: false,
  estimated_monthly_cost: "",
  risk_level: "",
  catalog_service_name: "",
};

function useOpenStackData() {
  const [data, setData] = useState({
    status: null,
    servers: [],
    images: [],
    flavors: [],
    networks: [],
    floatingIps: [],
    catalogServices: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [providerReachable, setProviderReachable] = useState(true);

  async function refresh() {
    setLoading(true);
    setError("");

    const openStackRequests = [
      ["status", api.getStatus()],
      ["servers", api.listServers()],
      ["images", api.listImages()],
      ["flavors", api.listFlavors()],
      ["networks", api.listNetworks()],
      ["floatingIps", api.listFloatingIps()],
    ];

    const [openStackResults, catalogResult] = await Promise.all([
      Promise.allSettled(openStackRequests.map(([, request]) => request)),
      api.listCatalogServices().then(
        (value) => ({ status: "fulfilled", value }),
        (reason) => ({ status: "rejected", reason }),
      ),
    ]);

    const nextData = {
      status: null,
      servers: [],
      images: [],
      flavors: [],
      networks: [],
      floatingIps: [],
      catalogServices: [],
    };
    let openStackErrorCount = 0;

    openStackResults.forEach((result, index) => {
      const key = openStackRequests[index][0];
      if (result.status === "fulfilled") {
        nextData[key] = result.value;
        return;
      }

      openStackErrorCount += 1;
    });

    if (catalogResult.status === "fulfilled") {
      nextData.catalogServices = catalogResult.value;
    } else {
      setError(`Service catalog failed: ${catalogResult.reason.message}`);
    }

    setProviderReachable(openStackErrorCount === 0);
    setData(nextData);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
  }, []);

  return { data, loading, error, providerReachable, setError, refresh };
}

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [notice, setNotice] = useState("");
  const [toasts, setToasts] = useState([]);
  const [requestDefaults, setRequestDefaults] = useState(emptyCreateForm);
  const { data, loading, error, providerReachable, setError, refresh } = useOpenStackData();

  function showToast(message, type = "success") {
    const id = window.crypto?.randomUUID?.() ?? String(Date.now());
    setToasts((current) => [...current, { id, message, type }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 4200);
  }

  async function runAction(label, action) {
    setNotice("");
    setError("");
    try {
      const result = await action();
      const status = result?.status ?? "done";
      setNotice(`${label}: ${status}`);
      showToast(`${label}: ${status}`, "success");
      await refresh();
      return result;
    } catch (err) {
      setError(err.message);
      showToast(`${label} failed: ${err.message}`, "error");
      throw err;
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">OS</span>
          <div>
            <h1>OpenStack Portal</h1>
            <p>Self-service cloud operations</p>
          </div>
        </div>

        <nav className="nav-tabs" aria-label="Portal sections">
          {tabs.map((tab) => (
            <button
              className={activeTab === tab.id ? "active" : ""}
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">API</p>
            <strong>http://127.0.0.1:8000/api/v1</strong>
          </div>
          <button className="primary" disabled={loading} onClick={refresh} type="button">
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </header>

        {!providerReachable && (
          <div className="alert warning">OpenStack provider is currently unreachable.</div>
        )}
        {error && <div className="alert error">{error}</div>}
        {notice && <div className="alert success">{notice}</div>}

        {activeTab === "dashboard" && (
          <Dashboard data={data} loading={loading} providerReachable={providerReachable} />
        )}
        {activeTab === "catalog" && (
          <ServiceCatalog
            loading={loading}
            onRequest={(service) => {
              setRequestDefaults(buildCatalogRequestDefaults(service));
              setActiveTab("create");
              showToast(`${service.name} loaded into request form`, "success");
            }}
            services={data.catalogServices}
          />
        )}
        {activeTab === "servers" && (
          <ServersList
            loading={loading}
            providerReachable={providerReachable}
            servers={data.servers}
            onAction={runAction}
          />
        )}
        {activeTab === "create" && (
          <CreateVmForm
            flavors={data.flavors}
            images={data.images}
            initialValues={requestDefaults}
            networks={data.networks}
            onCreated={async (result) => {
              const message = getSubmissionMessage(result);
              setNotice(message);
              showToast(message, "success");
              await refresh();
            }}
            onError={setError}
          />
        )}
        {activeTab === "images" && <ImagesList images={data.images} />}
        {activeTab === "flavors" && <FlavorsList flavors={data.flavors} />}
        {activeTab === "networks" && <NetworksList networks={data.networks} />}
        {activeTab === "floatingIps" && (
          <FloatingIpsPanel
            floatingIps={data.floatingIps}
            providerReachable={providerReachable}
            servers={data.servers}
            onAction={runAction}
          />
        )}
      </main>

      <ToastStack
        onDismiss={(id) =>
          setToasts((current) => current.filter((toast) => toast.id !== id))
        }
        toasts={toasts}
      />
    </div>
  );
}

function ServiceCatalog({ loading, onRequest, services }) {
  return (
    <section className="catalog-page">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Catalog</p>
          <h2>Service Catalog</h2>
          <p className="dashboard-copy">
            Select a standard OpenStack service blueprint and submit it for policy review.
          </p>
        </div>
        <span className="status-pill">{services.length} services</span>
      </div>

      {loading && (
        <div className="catalog-loading">
          <span className="spinner" />
          <span>Loading catalog...</span>
        </div>
      )}

      <div className="catalog-grid">
        {services.map((service) => (
          <article className="catalog-card" key={service.id}>
            <div className="catalog-card-header">
              <div>
                <h3>{service.name}</h3>
                <p>{service.description}</p>
              </div>
              <span className={`risk-pill ${service.risk_level}`}>{service.risk_level}</span>
            </div>
            <dl className="catalog-specs">
              <Detail label="CPU" value={`${service.recommended_cpu} vCPU`} />
              <Detail label="RAM" value={`${service.recommended_ram_gb} GB`} />
              <Detail label="Disk" value={`${service.recommended_disk_gb} GB`} />
              <Detail label="Cost" value={formatCurrency(service.estimated_monthly_cost)} />
            </dl>
            <button className="primary" onClick={() => onRequest(service)} type="button">
              Request Service
            </button>
          </article>
        ))}
      </div>

      {!loading && services.length === 0 && (
        <div className="empty-state catalog-empty">
          <strong>No catalog services found</strong>
          <span>Check the catalog API and refresh the page.</span>
        </div>
      )}
    </section>
  );
}

function Dashboard({ data, loading, providerReachable }) {
  const status = providerReachable
    ? data.status?.status ?? (loading ? "loading" : "unknown")
    : "unavailable";
  const cloud = data.status?.cloud ?? {};
  const cards = [
    {
      label: "Total Images",
      value: providerReachable ? data.images.length : "Unavailable",
      helper: "Available boot sources",
      tone: "blue",
    },
    {
      label: "Total Flavors",
      value: providerReachable ? data.flavors.length : "Unavailable",
      helper: "Compute size options",
      tone: "green",
    },
    {
      label: "Total Networks",
      value: providerReachable ? data.networks.length : "Unavailable",
      helper: "Tenant and external networks",
      tone: "cyan",
    },
    {
      label: "Total Servers",
      value: providerReachable ? data.servers.length : "Unavailable",
      helper: "Provisioned instances",
      tone: "violet",
    },
    {
      label: "Floating IPs",
      value: providerReachable ? data.floatingIps.length : "Unavailable",
      helper: "Public address inventory",
      tone: "amber",
    },
  ];

  return (
    <section className="dashboard-page">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Overview</p>
          <h2>Cloud Dashboard</h2>
          <p className="dashboard-copy">
            Live OpenStack resource counts from the self-service API.
          </p>
        </div>
        <span className={`status-pill ${status}`}>{status}</span>
      </div>
      <div className="metric-grid">
        {cards.map((card) => (
          <MetricCard key={card.label} loading={loading} {...card} />
        ))}
      </div>
      <div className="details-panel">
        <h3>Cloud</h3>
        <dl>
          <Detail label="Project" value={cloud.project_name} />
          <Detail label="Region" value={cloud.region} />
          <Detail label="User" value={cloud.user_name} />
          <Detail label="Auth URL" value={cloud.auth_url} />
        </dl>
      </div>
    </section>
  );
}

function ServersList({ loading, providerReachable, servers, onAction }) {
  const [pendingServer, setPendingServer] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  async function runServerAction(actionKey, label, server, action) {
    setPendingServer(`${server.id}:${actionKey}`);
    try {
      await onAction(label, action);
    } finally {
      setPendingServer(null);
      setConfirmDelete(null);
    }
  }

  return (
    <section className="server-page">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Compute</p>
          <h2>Server Management</h2>
          <p className="dashboard-copy">
            View instances and run lifecycle actions against existing backend APIs.
          </p>
        </div>
        <span className="status-pill">{servers.length} servers</span>
      </div>

      <div className="server-table-card">
        {loading && (
          <div className="table-loading">
            <span className="spinner" />
            <span>Loading servers...</span>
          </div>
        )}

        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Image</th>
              <th>Flavor</th>
              <th>Private IP</th>
              <th>Floating IP</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {!loading &&
              servers.map((server) => {
                const ips = getServerIps(server.addresses);
                return (
                  <tr key={server.id}>
                    <td>
                      <strong>{server.name}</strong>
                      <small>{server.id}</small>
                    </td>
                    <td>
                      <span className={`server-status ${normalizeStatus(server.status)}`}>
                        {server.status ?? "unknown"}
                      </span>
                    </td>
                    <td>{server.image_id ?? "-"}</td>
                    <td>{server.flavor_id ?? "-"}</td>
                    <td>{ips.privateIp ?? "-"}</td>
                    <td>{ips.floatingIp ?? "-"}</td>
                    <td>
                      <div className="button-row server-actions">
                        <ActionButton
                          busy={pendingServer === `${server.id}:start`}
                          disabled={!providerReachable}
                          label="Start"
                          onClick={() =>
                            runServerAction("start", "Start server", server, () =>
                              api.startServer(server.id),
                            )
                          }
                        />
                        <ActionButton
                          busy={pendingServer === `${server.id}:stop`}
                          disabled={!providerReachable}
                          label="Stop"
                          onClick={() =>
                            runServerAction("stop", "Stop server", server, () =>
                              api.stopServer(server.id),
                            )
                          }
                        />
                        <ActionButton
                          busy={pendingServer === `${server.id}:soft-reboot`}
                          disabled={!providerReachable}
                          label="Soft Reboot"
                          onClick={() =>
                            runServerAction("soft-reboot", "Soft reboot server", server, () =>
                              api.rebootServer(server.id),
                            )
                          }
                        />
                        <ActionButton
                          busy={pendingServer === `${server.id}:hard-reboot`}
                          disabled={!providerReachable}
                          label="Hard Reboot"
                          onClick={() =>
                            runServerAction("hard-reboot", "Hard reboot server", server, () =>
                              api.hardRebootServer(server.id),
                            )
                          }
                        />
                        <button
                          className="danger"
                          disabled={!providerReachable}
                          onClick={() => setConfirmDelete(server)}
                          type="button"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            {!loading && servers.length === 0 && (
              <tr>
                <td className="empty-state-cell" colSpan={7}>
                  <div className="empty-state">
                    <strong>No servers found</strong>
                    <span>Create a VM to see it listed here.</span>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {confirmDelete && (
        <ConfirmDialog
          busy={pendingServer === `${confirmDelete.id}:delete`}
          description={`Delete server "${confirmDelete.name || confirmDelete.id}"? This action cannot be undone.`}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() =>
            runServerAction("delete", "Delete server", confirmDelete, () =>
              api.deleteServer(confirmDelete.id),
            )
          }
          title="Delete server"
        />
      )}
    </section>
  );
}

function CreateVmForm({ images, flavors, initialValues, networks, onCreated, onError }) {
  const [form, setForm] = useState(emptyCreateForm);
  const [saving, setSaving] = useState(false);
  const [lastSubmission, setLastSubmission] = useState(null);
  const governance = evaluateGovernancePreview(form);

  useEffect(() => {
    setForm({ ...emptyCreateForm, ...initialValues });
  }, [initialValues]);

  function updateField(event) {
    const { checked, name, type, value } = event.target;
    setForm((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    onError("");
    try {
      const payload = buildVmRequestPayload(form);
      const result = await api.submitVmRequest(payload);
      setLastSubmission(result);
      setForm(emptyCreateForm);
      await onCreated(result);
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className="section-title">
        <h2>VM Request</h2>
      </div>
      <form className="form-grid" onSubmit={submit}>
        <label>
          Name
          <input name="name" onChange={updateField} required value={form.name} />
        </label>
        <label>
          Image
          <select name="image_id" onChange={updateField} required value={form.image_id}>
            <option value="">Select image</option>
            {images.map((image) => (
              <option key={image.id} value={image.id}>
                {image.name || image.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Flavor
          <select name="flavor_id" onChange={updateField} required value={form.flavor_id}>
            <option value="">Select flavor</option>
            {flavors.map((flavor) => (
              <option key={flavor.id} value={flavor.id}>
                {flavor.name || flavor.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Network
          <select name="network_id" onChange={updateField} required value={form.network_id}>
            <option value="">Select network</option>
            {networks.map((network) => (
              <option key={network.id} value={network.id}>
                {network.name || network.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Key name
          <input name="key_name" onChange={updateField} value={form.key_name} />
        </label>
        <label>
          Security group ID
          <input
            name="security_group_id"
            onChange={updateField}
            value={form.security_group_id}
          />
        </label>
        <label>
          CPU
          <input min="1" name="cpu" onChange={updateField} required type="number" value={form.cpu} />
        </label>
        <label>
          RAM GB
          <input
            min="1"
            name="ram_gb"
            onChange={updateField}
            required
            type="number"
            value={form.ram_gb}
          />
        </label>
        <label>
          Disk GB
          <input
            min="1"
            name="disk_gb"
            onChange={updateField}
            required
            type="number"
            value={form.disk_gb}
          />
        </label>
        <label>
          Environment
          <select name="environment" onChange={updateField} required value={form.environment}>
            <option value="dev">dev</option>
            <option value="test">test</option>
            <option value="stage">stage</option>
            <option value="prod">prod</option>
          </select>
        </label>
        <label>
          App tag
          <input name="app_tag" onChange={updateField} required value={form.app_tag} />
        </label>
        <label>
          Cost center
          <input name="cost_center" onChange={updateField} required value={form.cost_center} />
        </label>
        <label>
          Lifetime days
          <input
            min="1"
            name="lifetime_days"
            onChange={updateField}
            required
            type="number"
            value={form.lifetime_days}
          />
        </label>
        <label>
          Packages
          <input
            name="packages"
            onChange={updateField}
            placeholder="python, git, docker"
            value={form.packages}
          />
        </label>
        <label>
          Estimated cost
          <input
            name="estimated_monthly_cost"
            onChange={updateField}
            readOnly
            value={
              form.estimated_monthly_cost
                ? formatCurrency(Number(form.estimated_monthly_cost))
                : ""
            }
          />
        </label>
        <label>
          Risk level
          <input name="risk_level" onChange={updateField} readOnly value={form.risk_level} />
        </label>
        <label className="checkbox-label">
          <input
            checked={form.public_ip_required}
            name="public_ip_required"
            onChange={updateField}
            type="checkbox"
          />
          Public IP required
        </label>
        <GovernancePreview evaluation={governance} serviceName={form.catalog_service_name} />
        <button className="primary form-submit" disabled={saving} type="submit">
          {saving ? "Submitting..." : "Submit Request"}
        </button>
      </form>
      {lastSubmission && <RequestSubmissionResult result={lastSubmission} />}
    </section>
  );
}

function RequestSubmissionResult({ result }) {
  const selectedCatalogItem = result.request?.catalog_service_name;

  return (
    <section className="request-result-panel">
      <div>
        <p className="eyebrow">Request</p>
        <h3>Submission Saved</h3>
      </div>
      <dl className="request-result-details">
        <Detail label="Request ID" value={result.id} />
        <Detail label="Status" value={formatDecision(result.status)} />
        <Detail label="Selected service" value={selectedCatalogItem} />
        <Detail label="Approval decision" value={formatDecision(result.policy?.final_decision)} />
        <Detail label="Governance score" value={result.policy?.governance_score} />
        <Detail
          label="Estimated cost"
          value={formatCurrency(result.policy?.estimated_monthly_cost)}
        />
      </dl>
      {result.provisioning_error && (
        <p className="request-result-note">
          Provisioning was not attempted successfully because OpenStack is unreachable. The
          request is saved and can be reviewed later.
        </p>
      )}
    </section>
  );
}

function GovernancePreview({ evaluation, serviceName }) {
  return (
    <section className="governance-panel">
      <div>
        <p className="eyebrow">Governance</p>
        <h3>Policy Evaluation</h3>
      </div>
      {serviceName && <p className="dashboard-copy">Selected service: {serviceName}</p>}
      <div className="governance-summary">
        <span className={`decision-pill ${evaluation.finalDecision}`}>
          {formatDecision(evaluation.finalDecision)}
        </span>
        <strong>Score {evaluation.score}</strong>
        <span>{formatDecision(evaluation.governanceDecision)}</span>
      </div>
      <dl className="governance-details">
        <Detail label="Estimated cost" value={formatCurrency(evaluation.estimatedMonthlyCost)} />
        <Detail label="Basic policy" value={formatDecision(evaluation.basicDecision)} />
      </dl>
      {evaluation.reasons.length > 0 ? (
        <ul className="governance-reasons">
          {evaluation.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-copy">No policy concerns detected.</p>
      )}
    </section>
  );
}

function ImagesList({ images }) {
  return (
    <ResourceTable
      columns={["Name", "Status", "Visibility", "Disk Format", "Size"]}
      emptyLabel="No images found"
      rows={images.map((image) => ({
        id: image.id,
        cells: [
          image.name || "-",
          image.status || "-",
          image.visibility || "-",
          image.disk_format || "-",
          formatSize(image.size),
        ],
      }))}
      title="Images"
    />
  );
}

function FlavorsList({ flavors }) {
  return (
    <ResourceTable
      columns={["Name", "vCPUs", "RAM", "Disk", "Public"]}
      emptyLabel="No flavors found"
      rows={flavors.map((flavor) => ({
        id: flavor.id,
        cells: [
          flavor.name || "-",
          flavor.vcpus ?? "-",
          `${flavor.ram ?? "-"} MB`,
          `${flavor.disk ?? "-"} GB`,
          flavor.is_public === null ? "-" : String(flavor.is_public),
        ],
      }))}
      title="Flavors"
    />
  );
}

function NetworksList({ networks }) {
  return (
    <ResourceTable
      columns={["Name", "Status", "Shared", "External", "Project"]}
      emptyLabel="No networks found"
      rows={networks.map((network) => ({
        id: network.id,
        cells: [
          network.name || "-",
          network.status || "-",
          String(network.is_shared ?? "-"),
          String(network.is_router_external ?? "-"),
          network.project_id || "-",
        ],
      }))}
      title="Networks"
    />
  );
}

function FloatingIpsPanel({ floatingIps, providerReachable, servers, onAction }) {
  const [selectedServer, setSelectedServer] = useState("");
  const [selectedIp, setSelectedIp] = useState("");

  const availableIps = useMemo(
    () => floatingIps.filter((ip) => !ip.port_id && ip.floating_ip_address),
    [floatingIps],
  );

  return (
    <section>
      <div className="section-title">
        <h2>Floating IPs</h2>
        <button
          className="primary"
          disabled={!providerReachable}
          onClick={() => onAction("Allocate floating IP", api.createFloatingIp)}
          type="button"
        >
          Allocate
        </button>
      </div>

      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!providerReachable) {
            return;
          }
          onAction("Attach floating IP", () => api.attachFloatingIp(selectedServer, selectedIp));
        }}
      >
        <select
          onChange={(event) => setSelectedServer(event.target.value)}
          required
          value={selectedServer}
        >
          <option value="">Select server</option>
          {servers.map((server) => (
            <option key={server.id} value={server.id}>
              {server.name || server.id}
            </option>
          ))}
        </select>
        <select onChange={(event) => setSelectedIp(event.target.value)} required value={selectedIp}>
          <option value="">Select floating IP</option>
          {availableIps.map((ip) => (
            <option key={ip.id} value={ip.floating_ip_address}>
              {ip.floating_ip_address}
            </option>
          ))}
        </select>
        <button disabled={!providerReachable} type="submit">
          Attach
        </button>
      </form>

      <ResourceTable
        columns={["Address", "Status", "Network", "Port", "Fixed IP"]}
        emptyLabel="No floating IPs found"
        rows={floatingIps.map((ip) => ({
          id: ip.id,
          cells: [
            ip.floating_ip_address || "-",
            ip.status || "-",
            ip.floating_network_id || "-",
            ip.port_id || "-",
            ip.fixed_ip_address || "-",
          ],
        }))}
      />
    </section>
  );
}

function ResourceTable({ title, columns, rows, emptyLabel }) {
  return (
    <section>
      {title && (
        <div className="section-title">
          <h2>{title}</h2>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                {row.cells.map((cell, index) => (
                  <td key={`${row.id}-${index}`}>{cell}</td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && <EmptyRow colSpan={columns.length} label={emptyLabel} />}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MetricCard({ label, value, helper, tone, loading }) {
  const isUnavailable = value === "Unavailable";
  return (
    <div className={`metric-card ${tone}`}>
      <div className="metric-card-top">
        <span>{label}</span>
        <i aria-hidden="true" />
      </div>
      {loading ? (
        <div className="metric-skeleton" />
      ) : (
        <strong className={isUnavailable ? "unavailable-value" : ""}>{value}</strong>
      )}
      <p>{helper}</p>
    </div>
  );
}

function ActionButton({ busy, disabled = false, label, onClick }) {
  return (
    <button disabled={busy || disabled} onClick={onClick} type="button">
      {busy ? <span className="spinner small" /> : null}
      {busy ? "Working" : label}
    </button>
  );
}

function ConfirmDialog({ busy, description, onCancel, onConfirm, title }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div aria-modal="true" className="confirm-dialog" role="dialog">
        <h3>{title}</h3>
        <p>{description}</p>
        <div className="modal-actions">
          <button disabled={busy} onClick={onCancel} type="button">
            Cancel
          </button>
          <button className="danger solid" disabled={busy} onClick={onConfirm} type="button">
            {busy ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ToastStack({ onDismiss, toasts }) {
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <div className={`toast ${toast.type}`} key={toast.id}>
          <span>{toast.message}</span>
          <button onClick={() => onDismiss(toast.id)} type="button">
            Dismiss
          </button>
        </div>
      ))}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value === null || value === undefined || value === "" ? "-" : value}</dd>
    </>
  );
}

function EmptyRow({ colSpan, label }) {
  return (
    <tr>
      <td className="empty" colSpan={colSpan}>
        {label}
      </td>
    </tr>
  );
}

function formatAddresses(addresses) {
  if (!addresses || Object.keys(addresses).length === 0) {
    return "-";
  }

  return Object.entries(addresses)
    .map(([network, values]) => {
      const addressList = Array.isArray(values)
        ? values.map((item) => item.addr ?? item).join(", ")
        : String(values);
      return `${network}: ${addressList}`;
    })
    .join(" | ");
}

function getServerIps(addresses) {
  const flattened = Object.values(addresses ?? {})
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .filter(Boolean);

  const privateIp =
    flattened.find((item) => item?.["OS-EXT-IPS:type"] === "fixed")?.addr ??
    flattened.find((item) => isPrivateIp(item?.addr))?.addr;
  const floatingIp =
    flattened.find((item) => item?.["OS-EXT-IPS:type"] === "floating")?.addr ??
    flattened.find((item) => item?.addr && !isPrivateIp(item.addr))?.addr;

  return { privateIp, floatingIp };
}

function isPrivateIp(ipAddress) {
  if (!ipAddress) {
    return false;
  }

  return /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)/.test(ipAddress);
}

function normalizeStatus(status) {
  return String(status ?? "unknown").toLowerCase().replaceAll(" ", "-");
}

function buildCatalogRequestDefaults(service) {
  return {
    ...emptyCreateForm,
    name: service.id,
    cpu: String(service.recommended_cpu),
    ram_gb: String(service.recommended_ram_gb),
    disk_gb: String(service.recommended_disk_gb),
    environment: service.environment,
    app_tag: service.app_tag,
    lifetime_days: "30",
    packages: service.packages.join(", "),
    public_ip_required: service.public_ip_required,
    estimated_monthly_cost: String(service.estimated_monthly_cost ?? ""),
    risk_level: service.risk_level ?? "",
    catalog_service_name: service.name ?? "",
  };
}

function buildVmRequestPayload(form) {
  const payload = {
    name: form.name,
    image_id: form.image_id,
    flavor_id: form.flavor_id,
    network_id: form.network_id,
    cpu: Number(form.cpu),
    ram_gb: Number(form.ram_gb),
    disk_gb: Number(form.disk_gb),
    environment: form.environment,
    app_tag: form.app_tag,
    cost_center: form.cost_center,
    lifetime_days: Number(form.lifetime_days),
    packages: form.packages
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    public_ip_required: form.public_ip_required,
  };

  if (form.security_group_id.trim()) {
    payload.security_group_id = form.security_group_id.trim();
  }

  if (form.key_name.trim()) {
    payload.key_name = form.key_name.trim();
  }

  if (form.catalog_service_name.trim()) {
    payload.catalog_service_name = form.catalog_service_name.trim();
  }

  return payload;
}

function getSubmissionMessage(result) {
  if (!result?.id) {
    return "VM request submitted";
  }

  return `VM request ${result.id} saved as ${formatDecision(result.status)}`;
}

function formatCurrency(value) {
  if (!Number.isFinite(Number(value))) {
    return "-";
  }

  return new Intl.NumberFormat("en-IN", {
    currency: "INR",
    maximumFractionDigits: 0,
    style: "currency",
  }).format(Number(value));
}

function evaluateGovernancePreview(form) {
  const cpu = Number(form.cpu || 0);
  const ramGb = Number(form.ram_gb || 0);
  const diskGb = Number(form.disk_gb || 0);
  const environment = String(form.environment || "").toLowerCase();
  const publicIpRequired = Boolean(form.public_ip_required);
  const catalogCost = Number(form.estimated_monthly_cost);
  const estimatedMonthlyCost = Number.isFinite(catalogCost) && catalogCost > 0
    ? catalogCost
    : cpu * 500 + ramGb * 150 + diskGb * 5;
  const reasons = [];

  const basicAutoApproved =
    cpu <= 6 &&
    ramGb <= 12 &&
    diskGb <= 200 &&
    environment !== "prod" &&
    !publicIpRequired;

  let score = 0;

  if (estimatedMonthlyCost > 5000) {
    score += 30;
    reasons.push("Estimated monthly cost is greater than 5000");
  }

  if (publicIpRequired) {
    score += 30;
    reasons.push("Public IP requested");
  }

  if (environment === "prod") {
    score += 20;
    reasons.push("Production workload");
  }

  if (isCustomImage(form.image_id)) {
    score += 15;
    reasons.push("Custom image requested");
  }

  if (diskGb > 200) {
    score += 20;
    reasons.push("Disk size is greater than 200GB");
  }

  const governanceDecision =
    score <= 30 ? "auto_provision" : score <= 60 ? "auto_provision_notify" : "approval_required";
  const finalDecision =
    basicAutoApproved && governanceDecision !== "approval_required"
      ? "auto_approved"
      : "approval_required";

  if (!basicAutoApproved) {
    reasons.push("Basic auto-approval policy was not satisfied");
  }

  return {
    basicDecision: basicAutoApproved ? "auto_approved" : "approval_required",
    estimatedMonthlyCost,
    finalDecision,
    governanceDecision,
    reasons,
    score,
  };
}

function isCustomImage(imageId) {
  const normalized = String(imageId || "").toLowerCase();
  return normalized.startsWith("custom:") || normalized.includes("custom");
}

function formatDecision(value) {
  return String(value || "-").replaceAll("_", " ");
}

function formatSize(size) {
  if (!size) {
    return "-";
  }

  if (size < 1024 * 1024 * 1024) {
    return `${Math.round(size / 1024 / 1024)} MB`;
  }

  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
}
