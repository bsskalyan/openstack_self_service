import React, { useEffect, useMemo, useState } from "react";

import { api } from "./api";

const tabs = [
  { id: "dashboard", label: "Dashboard" },
  { id: "catalog", label: "Service Catalog" },
  { id: "requests", label: "My Requests" },
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
    securityGroups: [],
    keypairs: [],
    floatingIps: [],
    catalogServices: [],
    vmRequests: [],
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
      ["securityGroups", api.listSecurityGroups()],
      ["keypairs", api.listKeypairs()],
      ["floatingIps", api.listFloatingIps()],
    ];

    const [openStackResults, catalogResult, vmRequestsResult] = await Promise.all([
      Promise.allSettled(openStackRequests.map(([, request]) => request)),
      api.listCatalogServices().then(
        (value) => ({ status: "fulfilled", value }),
        (reason) => ({ status: "rejected", reason }),
      ),
      api.listVmRequests().then(
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
      securityGroups: [],
      keypairs: [],
      floatingIps: [],
      catalogServices: [],
      vmRequests: [],
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

    if (vmRequestsResult.status === "fulfilled") {
      nextData.vmRequests = vmRequestsResult.value;
    } else {
      setError(`VM requests failed: ${vmRequestsResult.reason.message}`);
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
        {activeTab === "requests" && (
          <MyRequestsPage
            loading={loading}
            onError={setError}
            requests={data.vmRequests}
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
            keypairs={data.keypairs}
            networks={data.networks}
            providerReachable={providerReachable}
            securityGroups={data.securityGroups}
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

function MyRequestsPage({ loading, onError, requests }) {
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  async function openRequest(requestId) {
    setDetailsLoading(true);
    onError("");
    try {
      const result = await api.getVmRequest(requestId);
      setSelectedRequest(result);
    } catch (err) {
      onError(err.message);
    } finally {
      setDetailsLoading(false);
    }
  }

  return (
    <section className="requests-page">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Governance</p>
          <h2>My Requests</h2>
          <p className="dashboard-copy">
            Review submitted service requests, policy decisions, and provisioning results.
          </p>
        </div>
        <span className="status-pill">{requests.length} requests</span>
      </div>

      <div className="requests-layout">
        <div className="server-table-card requests-table">
          {loading && (
            <div className="table-loading">
              <span className="spinner" />
              <span>Loading requests...</span>
            </div>
          )}
          <table>
            <thead>
              <tr>
                <th>Request ID</th>
                <th>Catalog Item</th>
                <th>Status</th>
                <th>Governance Score</th>
                <th>Approval Decision</th>
                <th>Estimated Cost</th>
                <th>Created Time</th>
                <th>Provider</th>
              </tr>
            </thead>
            <tbody>
              {!loading &&
                requests.map((request) => (
                  <tr
                    className="clickable-row"
                    key={request.id}
                    onClick={() => openRequest(request.id)}
                  >
                    <td>
                      <strong>{shortId(request.id)}</strong>
                      <small>{request.id}</small>
                    </td>
                    <td>{request.request?.catalog_service_name || request.request?.app_tag || "-"}</td>
                    <td>
                      <span className={`request-status ${normalizeStatus(request.status)}`}>
                        {formatDecision(request.status)}
                      </span>
                    </td>
                    <td>{request.policy?.governance_score ?? "-"}</td>
                    <td>{formatDecision(request.policy?.final_decision)}</td>
                    <td>{formatCurrency(request.policy?.estimated_monthly_cost)}</td>
                    <td>{formatDateTime(request.created_at)}</td>
                    <td>OpenStack</td>
                  </tr>
                ))}
              {!loading && requests.length === 0 && (
                <tr>
                  <td className="empty-state-cell" colSpan={8}>
                    <div className="empty-state">
                      <strong>No requests found</strong>
                      <span>Submit a catalog request to see it here.</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <RequestDetailsPanel
          loading={detailsLoading}
          request={selectedRequest}
          onClose={() => setSelectedRequest(null)}
        />
      </div>
    </section>
  );
}

function RequestDetailsPanel({ loading, onClose, request }) {
  if (!request && !loading) {
    return (
      <aside className="request-details-panel empty-panel">
        <p className="eyebrow">Details</p>
        <h3>Select a request</h3>
        <p className="dashboard-copy">Click any request row to inspect its payload and policy.</p>
      </aside>
    );
  }

  if (loading) {
    return (
      <aside className="request-details-panel empty-panel">
        <span className="spinner" />
        <p>Loading request details...</p>
      </aside>
    );
  }

  const policy = request.policy ?? {};
  const payload = request.request ?? {};

  return (
    <aside className="request-details-panel">
      <div className="request-details-header">
        <div>
          <p className="eyebrow">Details</p>
          <h3>{payload.name || shortId(request.id)}</h3>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </div>

      <dl className="request-result-details">
        <Detail label="Request ID" value={request.id} />
        <Detail label="Status" value={formatDecision(request.status)} />
        <Detail label="Selected service" value={payload.catalog_service_name} />
        <Detail label="Provider" value="OpenStack" />
        <Detail label="Approval decision" value={formatDecision(policy.final_decision)} />
        <Detail label="Governance decision" value={formatDecision(policy.governance_decision)} />
        <Detail label="Governance score" value={policy.governance_score} />
        <Detail label="Estimated cost" value={formatCurrency(policy.estimated_monthly_cost)} />
        <Detail label="Created" value={formatDateTime(request.created_at)} />
      </dl>

      <section className="details-section">
        <h4>Governance Score Breakdown</h4>
        {policy.reasons?.length > 0 ? (
          <ul className="governance-reasons">
            {policy.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p className="dashboard-copy">No policy concerns detected.</p>
        )}
      </section>

      <JsonBlock title="Full Request Payload" value={payload} />
      <JsonBlock title="Policy Evaluation" value={policy} />
      <JsonBlock title="Created VM / Server" value={request.server} />

      {request.provisioning_error && (
        <p className="request-result-note">{request.provisioning_error}</p>
      )}
    </aside>
  );
}

function JsonBlock({ title, value }) {
  return (
    <section className="details-section">
      <h4>{title}</h4>
      <pre>{JSON.stringify(value ?? null, null, 2)}</pre>
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

function CreateVmForm({
  images,
  flavors,
  initialValues,
  keypairs,
  networks,
  providerReachable,
  securityGroups,
  onCreated,
  onError,
}) {
  const [form, setForm] = useState(emptyCreateForm);
  const [saving, setSaving] = useState(false);
  const [lastSubmission, setLastSubmission] = useState(null);
  const governance = evaluateGovernancePreview(form);
  const providerSelectionDisabled = !providerReachable && Boolean(form.catalog_service_name);

  useEffect(() => {
    setForm(
      buildCreateFormInitialValues(initialValues, {
        flavors,
        images,
        keypairs,
        networks,
        providerReachable,
        securityGroups,
      }),
    );
  }, [flavors, images, initialValues, keypairs, networks, providerReachable, securityGroups]);

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
          <select
            disabled={providerSelectionDisabled}
            name="image_id"
            onChange={updateField}
            required
            value={form.image_id}
          >
            <option value="">Select image</option>
            {providerSelectionDisabled && (
              <option value="auto:image">Selected automatically</option>
            )}
            {images.map((image) => (
              <option key={image.id} value={image.id}>
                {image.name || image.id}
              </option>
            ))}
          </select>
          {providerSelectionDisabled && (
            <span className="field-hint">
              Will be selected automatically when the provider becomes available.
            </span>
          )}
        </label>
        <label>
          Flavor
          <select
            disabled={providerSelectionDisabled}
            name="flavor_id"
            onChange={updateField}
            required
            value={form.flavor_id}
          >
            <option value="">Select flavor</option>
            {providerSelectionDisabled && (
              <option value="auto:flavor">Selected automatically</option>
            )}
            {flavors.map((flavor) => (
              <option key={flavor.id} value={flavor.id}>
                {flavor.name || flavor.id}
              </option>
            ))}
          </select>
          {providerSelectionDisabled && (
            <span className="field-hint">
              Will be selected automatically when the provider becomes available.
            </span>
          )}
        </label>
        <label>
          Network
          <select
            disabled={providerSelectionDisabled}
            name="network_id"
            onChange={updateField}
            required
            value={form.network_id}
          >
            <option value="">Select network</option>
            {providerSelectionDisabled && (
              <option value="auto:network">Selected automatically</option>
            )}
            {networks.map((network) => (
              <option key={network.id} value={network.id}>
                {network.name || network.id}
              </option>
            ))}
          </select>
          {providerSelectionDisabled && (
            <span className="field-hint">
              Will be selected automatically when the provider becomes available.
            </span>
          )}
        </label>
        <label>
          Keypair
          <select
            disabled={providerSelectionDisabled}
            name="key_name"
            onChange={updateField}
            value={form.key_name}
          >
            <option value="">No keypair</option>
            {providerSelectionDisabled && (
              <option value="auto:keypair">Selected automatically</option>
            )}
            {keypairs.map((keypair) => (
              <option key={keypair.name} value={keypair.name}>
                {keypair.name}
              </option>
            ))}
          </select>
          {providerSelectionDisabled && (
            <span className="field-hint">
              Will be selected automatically when the provider becomes available.
            </span>
          )}
        </label>
        <label>
          Security group
          <select
            disabled={providerSelectionDisabled}
            name="security_group_id"
            onChange={updateField}
            value={form.security_group_id}
          >
            <option value="">No security group</option>
            {providerSelectionDisabled && (
              <option value="auto:security-group">Selected automatically</option>
            )}
            {securityGroups.map((securityGroup) => (
              <option key={securityGroup.id} value={securityGroup.id}>
                {securityGroup.name || securityGroup.id}
              </option>
            ))}
          </select>
          {providerSelectionDisabled && (
            <span className="field-hint">
              Will be selected automatically when the provider becomes available.
            </span>
          )}
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
  const display = buildGovernanceDisplay(evaluation, serviceName);

  return (
    <section className="governance-panel">
      <div>
        <p className="eyebrow">Governance</p>
        <h3>Governance Evaluation</h3>
      </div>
      {serviceName && <p className="dashboard-copy">Selected service: {serviceName}</p>}

      <div className="governance-hero">
        <span className={`decision-pill ${evaluation.finalDecision}`}>{display.decision}</span>
        <strong>Score {evaluation.score}</strong>
        <span>{display.governanceAction}</span>
      </div>

      <dl className="governance-cards">
        <div>
          <dt>Decision</dt>
          <dd className={evaluation.finalDecision}>{display.decision}</dd>
        </div>
        <div>
          <dt>Estimated Cost</dt>
          <dd>{formatCurrency(evaluation.estimatedMonthlyCost)} / month</dd>
        </div>
        <div>
          <dt>Risk Score</dt>
          <dd>{evaluation.score} / 100</dd>
        </div>
        <div>
          <dt>Next Action</dt>
          <dd>{display.nextAction}</dd>
        </div>
      </dl>

      <div className="governance-reason-block">
        <h4>Reason</h4>
        <ul className="governance-reasons">
          {display.reasons.map((reason) => (
            <li className={reason.tone} key={reason.label}>
              <span>{reason.tone === "positive" ? "✓" : "!"}</span>
              {reason.label}
            </li>
          ))}
        </ul>
      </div>
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

function shortId(value) {
  return String(value || "-").slice(0, 8);
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function buildCreateFormInitialValues(
  initialValues,
  { flavors, images, keypairs, networks, providerReachable, securityGroups },
) {
  const nextValues = { ...emptyCreateForm, ...initialValues };

  if (!nextValues.catalog_service_name) {
    return nextValues;
  }

  if (!providerReachable) {
    return {
      ...nextValues,
      image_id: "auto:image",
      flavor_id: "auto:flavor",
      network_id: "auto:network",
      key_name: "auto:keypair",
      security_group_id: "auto:security-group",
    };
  }

  return {
    ...nextValues,
    image_id: nextValues.image_id || selectDefaultImage(images)?.id || "",
    flavor_id: nextValues.flavor_id || selectDefaultFlavor(flavors, nextValues)?.id || "",
    network_id: nextValues.network_id || selectDefaultNetwork(networks)?.id || "",
    key_name: nextValues.key_name || selectDefaultKeypair(keypairs)?.name || "",
    security_group_id:
      nextValues.security_group_id || selectDefaultSecurityGroup(securityGroups)?.id || "",
  };
}

function selectDefaultImage(images) {
  return (
    images.find((image) => normalizeStatus(image.status) === "active") ??
    images.find((image) => image.id) ??
    null
  );
}

function selectDefaultFlavor(flavors, form) {
  const requestedCpu = Number(form.cpu || 0);
  const requestedRamMb = Number(form.ram_gb || 0) * 1024;
  const requestedDiskGb = Number(form.disk_gb || 0);
  const sortedFlavors = [...flavors].sort((left, right) => {
    const leftWeight =
      Number(left.vcpus || 0) * 1_000_000 +
      Number(left.ram || 0) * 1_000 +
      Number(left.disk || 0);
    const rightWeight =
      Number(right.vcpus || 0) * 1_000_000 +
      Number(right.ram || 0) * 1_000 +
      Number(right.disk || 0);
    return leftWeight - rightWeight;
  });

  return (
    sortedFlavors.find(
      (flavor) =>
        Number(flavor.vcpus || 0) >= requestedCpu &&
        Number(flavor.ram || 0) >= requestedRamMb &&
        Number(flavor.disk || 0) >= requestedDiskGb,
    ) ??
    sortedFlavors.find((flavor) => flavor.id) ??
    null
  );
}

function selectDefaultNetwork(networks) {
  return (
    networks.find((network) => !network.is_router_external && normalizeStatus(network.status) === "active") ??
    networks.find((network) => !network.is_router_external) ??
    networks.find((network) => network.id) ??
    null
  );
}

function selectDefaultSecurityGroup(securityGroups) {
  return (
    securityGroups.find((securityGroup) => securityGroup.name === "default") ??
    securityGroups.find((securityGroup) => securityGroup.id) ??
    null
  );
}

function selectDefaultKeypair(keypairs) {
  return keypairs.find((keypair) => keypair.name) ?? null;
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

function buildGovernanceDisplay(evaluation, serviceName) {
  const isApprovalRequired = evaluation.finalDecision === "approval_required";
  const isNotify = evaluation.governanceDecision === "auto_provision_notify";

  if (isApprovalRequired) {
    return {
      decision: "Approval Required",
      governanceAction: "Approval Required",
      nextAction: "Request will be routed for approval.",
      reasons: evaluation.reasons.map((reason) => ({
        label: reason,
        tone: "warning",
      })),
    };
  }

  return {
    decision: isNotify ? "🟢 Auto Approved + Notify" : "🟢 Auto Approved",
    governanceAction: isNotify ? "Auto Provision + Notify" : "Auto Provision",
    nextAction: isNotify
      ? "VM will be provisioned automatically and stakeholders will be notified."
      : "VM will be provisioned automatically.",
    reasons: [
      { label: "Cost within allowed budget", tone: "positive" },
      { label: "Compute within auto-approval limits", tone: "positive" },
      { label: "Internal network only", tone: "positive" },
      {
        label: serviceName ? "Approved service template" : "Approved request template",
        tone: "positive",
      },
    ],
  };
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
