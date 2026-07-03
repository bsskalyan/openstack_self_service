import React, { useEffect, useMemo, useState } from "react";

import { api, setApiUser } from "./api";

const mockUsers = [
  { id: "engineer", name: "Asha Engineer", role: "engineer", label: "Engineer" },
  { id: "admin", name: "Morgan Admin", role: "admin", label: "Admin" },
  { id: "viewer", name: "Vik Viewer", role: "viewer", label: "Viewer" },
];

const tabs = [
  { id: "dashboard", label: "Dashboard", roles: ["engineer", "admin", "viewer"] },
  { id: "catalog", label: "Service Catalog", roles: ["engineer", "admin", "viewer"] },
  { id: "activity", label: "Activity", roles: ["engineer", "admin", "viewer"] },
  { id: "requests", label: "My Requests", roles: ["engineer", "admin"] },
  { id: "admin", label: "Admin", roles: ["admin"] },
  { id: "servers", label: "Servers", roles: ["engineer", "admin", "viewer"] },
  { id: "create", label: "Create VM", roles: ["engineer", "admin"] },
  { id: "images", label: "Images", roles: ["engineer", "admin", "viewer"] },
  { id: "flavors", label: "Flavors", roles: ["engineer", "admin", "viewer"] },
  { id: "networks", label: "Networks", roles: ["engineer", "admin", "viewer"] },
  { id: "floatingIps", label: "Floating IPs", roles: ["engineer", "admin", "viewer"] },
];

const applicationTypeOptions = ["Web", "API", "Database", "Batch", "AI/ML", "Other"];
const environmentOptions = [
  { label: "Development", value: "Development" },
  { label: "Test", value: "Test" },
  { label: "QA", value: "QA" },
  { label: "UAT", value: "UAT" },
  { label: "Production", value: "Production" },
];
const lifetimeOptions = [
  { label: "1 Day", value: "1_day", days: 1 },
  { label: "7 Days", value: "7_days", days: 7 },
  { label: "30 Days", value: "30_days", days: 30 },
  { label: "90 Days", value: "90_days", days: 90 },
  { label: "Permanent", value: "permanent", days: 0 },
];
const packageOptions = [
  "Docker",
  "Podman",
  "Nginx",
  "Apache",
  "Node.js",
  "Python",
  "PostgreSQL",
  "MySQL",
  "Git",
  "Ansible",
];

const emptyCreateForm = {
  project_name: "",
  business_unit: "",
  request_owner: "",
  team_name: "",
  application_name: "",
  application_type: "Web",
  purpose_description: "",
  name: "",
  image_id: "",
  flavor_id: "",
  network_id: "",
  key_name: "",
  security_group_id: "",
  cpu: "",
  ram_gb: "",
  disk_gb: "",
  environment: "Development",
  app_tag: "",
  cost_center: "",
  lifetime: "30_days",
  lifetime_days: "30",
  packages: [],
  public_ip_required: false,
  estimated_monthly_cost: "",
  risk_level: "",
  catalog_service_name: "",
};

function useOpenStackData(currentUser) {
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
    pendingRequests: [],
    auditEvents: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [providerReachable, setProviderReachable] = useState(true);

  async function refresh() {
    setApiUser(currentUser);
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

    const vmRequestsPromise =
      currentUser.role === "viewer"
        ? Promise.resolve({ status: "fulfilled", value: [] })
        : api.listVmRequests().then(
            (value) => ({ status: "fulfilled", value }),
            (reason) => ({ status: "rejected", reason }),
          );
    const pendingRequestsPromise =
      currentUser.role === "admin"
        ? api.listPendingVmRequests().then(
            (value) => ({ status: "fulfilled", value }),
            (reason) => ({ status: "rejected", reason }),
          )
        : Promise.resolve({ status: "fulfilled", value: [] });
    const auditPromise = api.listAuditEvents().then(
      (value) => ({ status: "fulfilled", value }),
      (reason) => ({ status: "rejected", reason }),
    );

    const [
      openStackResults,
      catalogResult,
      vmRequestsResult,
      pendingRequestsResult,
      auditResult,
    ] = await Promise.all([
      Promise.allSettled(openStackRequests.map(([, request]) => request)),
      api.listCatalogServices().then(
        (value) => ({ status: "fulfilled", value }),
        (reason) => ({ status: "rejected", reason }),
      ),
      vmRequestsPromise,
      pendingRequestsPromise,
      auditPromise,
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
      pendingRequests: [],
      auditEvents: [],
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

    if (pendingRequestsResult.status === "fulfilled") {
      nextData.pendingRequests = pendingRequestsResult.value;
    } else {
      setError(`Pending requests failed: ${pendingRequestsResult.reason.message}`);
    }

    if (auditResult.status === "fulfilled") {
      nextData.auditEvents = auditResult.value;
    } else {
      setError(`Activity failed: ${auditResult.reason.message}`);
    }

    setProviderReachable(openStackErrorCount === 0);
    setData(nextData);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
  }, [currentUser.name, currentUser.role]);

  return { data, loading, error, providerReachable, setError, refresh };
}

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [notice, setNotice] = useState("");
  const [toasts, setToasts] = useState([]);
  const [providers, setProviders] = useState([]);
  const [selectedProviderId, setSelectedProviderId] = useState("openstack");
  const [requestDefaults, setRequestDefaults] = useState(emptyCreateForm);
  const [currentUser, setCurrentUser] = useState(mockUsers[0]);
  const { data, loading, error, providerReachable, setError, refresh } =
    useOpenStackData(currentUser);
  const activeTabAllowed = canAccessTab(activeTab, currentUser.role);
  const selectedProvider =
    providers.find((provider) => provider.id === selectedProviderId) ??
    providers.find((provider) => provider.id === "openstack") ?? {
      id: "openstack",
      name: "OpenStack",
      status: "enabled",
      enabled: true,
      description: "OpenStack cloud provider",
    };

  useEffect(() => {
    setApiUser(currentUser);
    if (!canAccessTab(activeTab, currentUser.role)) {
      setActiveTab("dashboard");
      setNotice("Not authorized for that section with the selected role.");
    }
  }, [activeTab, currentUser]);

  useEffect(() => {
    api.listProviders().then(
      (value) => setProviders(value),
      (err) => setError(`Providers failed: ${err.message}`),
    );
  }, [setError]);

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
          {tabs
            .filter((tab) => tab.roles.includes(currentUser.role))
            .map((tab) => (
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
          <div className="topbar-actions">
            <ProviderSelector
              providers={providers}
              selectedProviderId={selectedProviderId}
              onChange={setSelectedProviderId}
            />
            <UserSelector currentUser={currentUser} onChange={setCurrentUser} />
            <button className="primary" disabled={loading} onClick={refresh} type="button">
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </header>

        {!providerReachable && (
          <div className="alert warning">OpenStack provider is currently unreachable.</div>
        )}
        {error && <div className="alert error">{error}</div>}
        {notice && <div className="alert success">{notice}</div>}

        {!activeTabAllowed && <NotAuthorized role={currentUser.role} />}

        {activeTabAllowed && activeTab === "dashboard" && (
          <Dashboard
            data={data}
            loading={loading}
            providerReachable={providerReachable}
            selectedProvider={selectedProvider}
          />
        )}
        {activeTabAllowed && activeTab === "catalog" && (
          <ServiceCatalog
            currentUser={currentUser}
            loading={loading}
            onRequest={(service) => {
              setRequestDefaults(buildCatalogRequestDefaults(service));
              setActiveTab("create");
              showToast(`${service.name} loaded into request form`, "success");
            }}
            selectedProvider={selectedProvider}
            services={data.catalogServices}
          />
        )}
        {activeTabAllowed && activeTab === "activity" && (
          <ActivityPage
            events={data.auditEvents}
            loading={loading}
            selectedProvider={selectedProvider}
            currentUser={currentUser}
          />
        )}
        {activeTabAllowed && activeTab === "requests" && (
          <MyRequestsPage
            currentUser={currentUser}
            loading={loading}
            onError={setError}
            requests={data.vmRequests}
            selectedProvider={selectedProvider}
          />
        )}
        {activeTabAllowed && activeTab === "admin" && (
          <AdminApprovalDashboard
            loading={loading}
            onError={setError}
            onRefresh={refresh}
            onToast={showToast}
            pendingRequests={data.pendingRequests}
            selectedProvider={selectedProvider}
          />
        )}
        {activeTabAllowed && activeTab === "servers" && (
          <ServersList
            currentUser={currentUser}
            loading={loading}
            providerReachable={providerReachable}
            servers={data.servers}
            selectedProvider={selectedProvider}
            vmRequests={data.vmRequests}
            onAction={runAction}
          />
        )}
        {activeTabAllowed && activeTab === "create" && (
          <CreateVmForm
            currentUser={currentUser}
            flavors={data.flavors}
            images={data.images}
            initialValues={requestDefaults}
            keypairs={data.keypairs}
            networks={data.networks}
            providerReachable={providerReachable}
            securityGroups={data.securityGroups}
            selectedProvider={selectedProvider}
            onCreated={async (result) => {
              const message = getSubmissionMessage(result);
              setNotice(message);
              showToast(message, "success");
              await refresh();
            }}
            onError={setError}
          />
        )}
        {activeTabAllowed && activeTab === "images" && <ImagesList images={data.images} />}
        {activeTabAllowed && activeTab === "flavors" && <FlavorsList flavors={data.flavors} />}
        {activeTabAllowed && activeTab === "networks" && <NetworksList networks={data.networks} />}
        {activeTabAllowed && activeTab === "floatingIps" && (
          <FloatingIpsPanel
            currentUser={currentUser}
            floatingIps={data.floatingIps}
            providerReachable={providerReachable}
            servers={data.servers}
            vmRequests={data.vmRequests}
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

function ProviderSelector({ onChange, providers, selectedProviderId }) {
  const options =
    providers.length > 0
      ? providers
      : [
          {
            id: "openstack",
            name: "OpenStack",
            status: "enabled",
            enabled: true,
          },
        ];

  return (
    <label className="provider-selector">
      <span>Provider</span>
      <select
        onChange={(event) => onChange(event.target.value)}
        value={selectedProviderId}
      >
        {options.map((provider) => (
          <option disabled={!provider.enabled} key={provider.id} value={provider.id}>
            {provider.name}: {provider.enabled ? "Enabled" : "Coming Soon"}
          </option>
        ))}
      </select>
    </label>
  );
}

function UserSelector({ currentUser, onChange }) {
  return (
    <label className="user-selector">
      <span>User</span>
      <select
        onChange={(event) => {
          const user = mockUsers.find((item) => item.id === event.target.value) ?? mockUsers[0];
          onChange(user);
        }}
        value={currentUser.id}
      >
        {mockUsers.map((user) => (
          <option key={user.id} value={user.id}>
            {user.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function NotAuthorized({ role }) {
  return (
    <section className="not-authorized-panel">
      <p className="eyebrow">RBAC</p>
      <h2>Not authorized</h2>
      <p>
        The selected {role} role can only access permitted OpenStack MVP sections. Choose a
        different mock user to continue.
      </p>
    </section>
  );
}

function ProviderBadge({ provider }) {
  return (
    <span className={`provider-badge ${provider.enabled ? "enabled" : "disabled"}`}>
      {provider.name} - {provider.enabled ? "Enabled" : "Coming Soon"}
    </span>
  );
}

function RoleBadge({ user }) {
  return (
    <span className={`role-badge ${user.role}`}>
      {user.label} - {user.name}
    </span>
  );
}

function ServiceCatalog({ currentUser, loading, onRequest, selectedProvider, services }) {
  const canRequest = canManageResources(currentUser.role);

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
        <div className="hero-actions">
          <ProviderBadge provider={selectedProvider} />
          <RoleBadge user={currentUser} />
          <span className="status-pill">{services.length} services</span>
        </div>
      </div>

      {!canRequest && (
        <div className="alert warning">Not authorized: viewers can browse the catalog only.</div>
      )}

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
            <button
              className="primary"
              disabled={!canRequest}
              onClick={() => onRequest(service)}
              type="button"
            >
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

function ActivityPage({ currentUser, events, loading, selectedProvider }) {
  return (
    <section className="activity-page">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Audit</p>
          <h2>Activity</h2>
          <p className="dashboard-copy">
            Recent OpenStack request, policy, provisioning, and lifecycle events.
          </p>
        </div>
        <div className="hero-actions">
          <ProviderBadge provider={selectedProvider} />
          <RoleBadge user={currentUser} />
          <span className="status-pill">{events.length} events</span>
        </div>
      </div>

      <AuditTimeline events={events} loading={loading} />
    </section>
  );
}

function MyRequestsPage({ currentUser, loading, onError, requests, selectedProvider }) {
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  async function openRequest(requestId) {
    setDetailsLoading(true);
    onError("");
    try {
      const [result, timeline] = await Promise.all([
        api.getVmRequest(requestId),
        api.getRequestTimeline(requestId),
      ]);
      setSelectedRequest({ ...result, timeline });
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
        <div className="hero-actions">
          <ProviderBadge provider={selectedProvider} />
          <RoleBadge user={currentUser} />
          <span className="status-pill">{requests.length} requests</span>
        </div>
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
                <th>Environment</th>
                <th>Lifetime</th>
                <th>Packages</th>
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
                    <td>{getRequestServiceName(request)}</td>
                    <td>
                      <span className={`request-status ${normalizeStatus(request.status)}`}>
                        {formatDecision(request.status)}
                      </span>
                    </td>
                    <td>{request.policy?.governance_score ?? "-"}</td>
                    <td>{formatDecision(request.policy?.final_decision)}</td>
                    <td>{formatCurrency(request.policy?.estimated_monthly_cost)}</td>
                    <td>{formatEnvironment(request.request?.environment)}</td>
                    <td>{formatLifetime(request.request)}</td>
                    <td>{formatPackages(request.request?.packages)}</td>
                    <td>{formatDateTime(request.created_at)}</td>
                    <td>OpenStack</td>
                  </tr>
                ))}
              {!loading && requests.length === 0 && (
                <tr>
                  <td className="empty-state-cell" colSpan={11}>
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

function AdminApprovalDashboard({
  loading,
  onError,
  onRefresh,
  onToast,
  pendingRequests,
  selectedProvider,
}) {
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState("");
  const [rejectReason, setRejectReason] = useState("");

  async function openRequest(requestId) {
    setDetailsLoading(true);
    onError("");
    try {
      const [result, timeline] = await Promise.all([
        api.getVmRequest(requestId),
        api.getRequestTimeline(requestId),
      ]);
      setSelectedRequest({ ...result, timeline });
      setRejectReason("");
    } catch (err) {
      onError(err.message);
    } finally {
      setDetailsLoading(false);
    }
  }

  async function approveRequest() {
    if (!selectedRequest) {
      return;
    }

    setActionLoading("approve");
    onError("");
    try {
      const result = await api.approveVmRequest(selectedRequest.id);
      setSelectedRequest(result);
      onToast(`Request ${shortId(result.id)} approved`, "success");
      await onRefresh();
    } catch (err) {
      onError(err.message);
      onToast(`Approval failed: ${err.message}`, "error");
    } finally {
      setActionLoading("");
    }
  }

  async function rejectRequest() {
    if (!selectedRequest) {
      return;
    }

    setActionLoading("reject");
    onError("");
    try {
      const result = await api.rejectVmRequest(selectedRequest.id, rejectReason.trim() || null);
      setSelectedRequest(result);
      onToast(`Request ${shortId(result.id)} rejected`, "success");
      await onRefresh();
    } catch (err) {
      onError(err.message);
      onToast(`Rejection failed: ${err.message}`, "error");
    } finally {
      setActionLoading("");
    }
  }

  return (
    <section className="admin-page">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Approval Dashboard</h2>
          <p className="dashboard-copy">
            Review requests that require approval before OpenStack provisioning.
          </p>
        </div>
        <div className="hero-actions">
          <ProviderBadge provider={selectedProvider} />
          <span className="status-pill">{pendingRequests.length} pending</span>
        </div>
      </div>

      <div className="requests-layout">
        <div className="server-table-card requests-table">
          {loading && (
            <div className="table-loading">
              <span className="spinner" />
              <span>Loading pending requests...</span>
            </div>
          )}
          <table>
            <thead>
              <tr>
                <th>Request ID</th>
                <th>User</th>
                <th>Service</th>
                <th>Cost</th>
                <th>Governance Score</th>
                <th>Environment</th>
                <th>Lifetime</th>
                <th>Packages</th>
                <th>Requested Resources</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {!loading &&
                pendingRequests.map((request) => (
                  <tr
                    className="clickable-row"
                    key={request.id}
                    onClick={() => openRequest(request.id)}
                  >
                    <td>
                      <strong>{shortId(request.id)}</strong>
                      <small>{request.id}</small>
                    </td>
                    <td>{getRequestUser(request)}</td>
                    <td>{getRequestServiceName(request)}</td>
                    <td>{formatCurrency(request.policy?.estimated_monthly_cost)}</td>
                    <td>{request.policy?.governance_score ?? "-"}</td>
                    <td>{formatEnvironment(request.request?.environment)}</td>
                    <td>{formatLifetime(request.request)}</td>
                    <td>{formatPackages(request.request?.packages)}</td>
                    <td>{formatRequestedResources(request.request)}</td>
                    <td>
                      <span className={`request-status ${normalizeStatus(request.status)}`}>
                        {formatDecision(request.status)}
                      </span>
                    </td>
                  </tr>
                ))}
              {!loading && pendingRequests.length === 0 && (
                <tr>
                  <td className="empty-state-cell" colSpan={10}>
                    <div className="empty-state">
                      <strong>No pending approvals</strong>
                      <span>Auto-approved, rejected, and provisioned requests do not appear here.</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <AdminRequestDetailsPanel
          actionLoading={actionLoading}
          loading={detailsLoading}
          onApprove={approveRequest}
          onClose={() => setSelectedRequest(null)}
          onReject={rejectRequest}
          rejectReason={rejectReason}
          request={selectedRequest}
          setRejectReason={setRejectReason}
        />
      </div>
    </section>
  );
}

function AdminRequestDetailsPanel({
  actionLoading,
  loading,
  onApprove,
  onClose,
  onReject,
  rejectReason,
  request,
  setRejectReason,
}) {
  if (!request && !loading) {
    return (
      <aside className="request-details-panel empty-panel">
        <p className="eyebrow">Approval</p>
        <h3>Select a request</h3>
        <p className="dashboard-copy">Click a pending request to review and decide.</p>
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
  const cost = getCostBreakdown(payload, policy);
  const failure = getFailureDetails(request);
  const canAct = request.status === "approval_required";

  return (
    <aside className="request-details-panel admin-details-panel">
      <div className="request-details-header">
        <div>
          <p className="eyebrow">Approval</p>
          <h3>{payload.catalog_service_name || payload.application_name || payload.name || shortId(request.id)}</h3>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </div>

      <dl className="request-result-details">
        <Detail label="Request ID" value={request.id} />
        <Detail label="User" value={getRequestUser(request)} />
        <Detail label="Status" value={formatDecision(request.status)} />
        <Detail label="Service" value={payload.catalog_service_name || payload.application_name || payload.app_tag} />
        <Detail label="Application Name" value={payload.application_name} />
        <Detail label="Application Type" value={payload.application_type} />
        <Detail label="Purpose" value={payload.purpose_description} />
        <Detail label="Environment" value={formatEnvironment(payload.environment)} />
        <Detail label="Lifetime" value={formatLifetime(payload)} />
        <Detail label="Expires at" value={formatDateTime(request.expires_at)} />
        <Detail label="Packages" value={formatPackages(payload.packages)} />
        <Detail label="Estimated cost" value={`${formatCurrency(policy.estimated_monthly_cost)} / month`} />
        <Detail label="Risk score" value={`${policy.governance_score ?? "-"} / 100`} />
        <Detail label="Approval decision" value={formatDecision(policy.final_decision)} />
        <Detail label="Resources" value={formatRequestedResources(payload)} />
      </dl>

      <LifecycleTimeline request={request} />
      <AuditTimeline events={request.timeline ?? []} compact title="Approval / Provisioning Timeline" />
      {failure && <FailureNotice failure={failure} />}
      <GovernanceExplanation policy={policy} request={payload} />
      <CostBreakdown cost={cost} />

      <JsonBlock title="Full Request" value={payload} />
      <JsonBlock title="Policy Evaluation" value={policy} />
      <ActivityLog entries={request.activity_log} />

      {canAct && (
        <section className="approval-actions">
          <label>
            Reject reason
            <textarea
              onChange={(event) => setRejectReason(event.target.value)}
              placeholder="Optional reason for rejection"
              rows={4}
              value={rejectReason}
            />
          </label>
          <div className="button-row">
            <button
              className="primary"
              disabled={Boolean(actionLoading)}
              onClick={onApprove}
              type="button"
            >
              {actionLoading === "approve" ? "Approving..." : "Approve"}
            </button>
            <button
              className="danger"
              disabled={Boolean(actionLoading)}
              onClick={onReject}
              type="button"
            >
              {actionLoading === "reject" ? "Rejecting..." : "Reject"}
            </button>
          </div>
        </section>
      )}

      {request.server && <JsonBlock title="Created VM / Server" value={request.server} />}
      {request.rejection_reason && (
        <p className="request-result-note">Rejected: {request.rejection_reason}</p>
      )}
    </aside>
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
  const cost = getCostBreakdown(payload, policy);
  const failure = getFailureDetails(request);

  return (
    <aside className="request-details-panel">
      <div className="request-details-header">
        <div>
          <p className="eyebrow">Details</p>
          <h3>{payload.application_name || payload.name || shortId(request.id)}</h3>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </div>

      <dl className="request-result-details">
        <Detail label="Request ID" value={request.id} />
        <Detail label="Status" value={formatDecision(request.status)} />
        <Detail label="Selected service" value={payload.catalog_service_name} />
        <Detail label="Application Name" value={payload.application_name} />
        <Detail label="Application Type" value={payload.application_type} />
        <Detail label="Purpose" value={payload.purpose_description} />
        <Detail label="Environment" value={formatEnvironment(payload.environment)} />
        <Detail label="Lifetime" value={formatLifetime(payload)} />
        <Detail label="Expires at" value={formatDateTime(request.expires_at)} />
        <Detail label="Packages" value={formatPackages(payload.packages)} />
        <Detail label="Provider" value="OpenStack" />
        <Detail label="Approval decision" value={formatDecision(policy.final_decision)} />
        <Detail label="Governance decision" value={formatDecision(policy.governance_decision)} />
        <Detail label="Governance score" value={policy.governance_score} />
        <Detail label="Estimated cost" value={formatCurrency(policy.estimated_monthly_cost)} />
        <Detail label="Created" value={formatDateTime(request.created_at)} />
      </dl>

      <LifecycleTimeline request={request} />
      <AuditTimeline events={request.timeline ?? []} compact title="Request Timeline" />
      {failure && <FailureNotice failure={failure} />}
      <GovernanceExplanation policy={policy} request={payload} />
      <CostBreakdown cost={cost} />

      <JsonBlock title="Full Request Payload" value={payload} />
      <JsonBlock title="Policy Evaluation" value={policy} />
      <JsonBlock title="Created VM / Server" value={request.server} />
      <ActivityLog entries={request.activity_log} />

      {!failure && request.provisioning_error && (
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

function FailureNotice({ failure }) {
  if (!failure) {
    return null;
  }

  return (
    <section className="failure-panel">
      <p className="eyebrow">Provisioning Error</p>
      <h4>{failure.user_message}</h4>
      <p>{failure.suggested_action}</p>
      <details>
        <summary>Admin/debug technical details</summary>
        <dl>
          <Detail label="Technical reason" value={failure.technical_reason} />
        </dl>
        <pre>{JSON.stringify(failure.raw_error ?? null, null, 2)}</pre>
      </details>
    </section>
  );
}

function LifecycleTimeline({ request }) {
  const steps = buildRequestTimeline(request);

  return (
    <section className="details-section">
      <h4>Request Lifecycle</h4>
      <ol className="timeline-list">
        {steps.map((step) => (
          <li className={step.state} key={step.label}>
            <span />
            <div>
              <strong>{step.label}</strong>
              <small>{step.time ? formatDateTime(step.time) : step.helper}</small>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function GovernanceExplanation({ policy, request }) {
  const reasons = buildGovernanceReasons(policy, request);

  return (
    <section className="details-section">
      <h4>Governance Score Explanation</h4>
      <div className="score-summary">
        <strong>{policy.governance_score ?? 0} / 100</strong>
        <span>{formatDecision(policy.final_decision)}</span>
      </div>
      <ul className="governance-reasons">
        {reasons.map((reason) => (
          <li className={reason.tone} key={reason.label}>
            <span>{reason.tone === "positive" ? "OK" : "!"}</span>
            {reason.label}
          </li>
        ))}
      </ul>
    </section>
  );
}

function CostBreakdown({ cost }) {
  return (
    <section className="details-section">
      <h4>Cost Breakdown</h4>
      <dl className="cost-breakdown">
        <Detail label="CPU" value={formatCurrency(cost.cpu)} />
        <Detail label="RAM" value={formatCurrency(cost.ram)} />
        <Detail label="Disk" value={formatCurrency(cost.disk)} />
        <Detail label="Estimated total" value={formatCurrency(cost.total)} />
      </dl>
    </section>
  );
}

function ActivityLog({ entries }) {
  const activity = entries?.length ? entries : [];

  return (
    <section className="details-section">
      <h4>Activity / Audit Log</h4>
      {activity.length > 0 ? (
        <ol className="activity-list">
          {activity.map((entry, index) => (
            <li key={`${entry.action}-${entry.created_at}-${index}`}>
              <strong>{formatDecision(entry.action)}</strong>
              <span>{entry.message}</span>
              <small>
                {entry.actor || "system"} - {formatDateTime(entry.created_at)}
              </small>
            </li>
          ))}
        </ol>
      ) : (
        <p className="dashboard-copy">No audit activity recorded yet.</p>
      )}
    </section>
  );
}

function AuditTimeline({ compact = false, events, loading = false, title = "Recent Activity" }) {
  const visibleEvents = events ?? [];

  return (
    <section className={compact ? "details-section audit-section compact" : "audit-section"}>
      <h4>{title}</h4>
      {loading && (
        <div className="table-loading inline-loading">
          <span className="spinner" />
          <span>Loading activity...</span>
        </div>
      )}
      {!loading && visibleEvents.length === 0 && (
        <p className="dashboard-copy">No activity recorded yet.</p>
      )}
      <ol className="audit-timeline">
        {visibleEvents.map((event) => (
          <li key={event.id}>
            <span className={`audit-dot ${normalizeStatus(event.status)}`} />
            <div>
              <strong>{formatDecision(event.action)}</strong>
              <p>{event.message}</p>
              <small>
                {formatDateTime(event.timestamp)} - {event.actor} ({event.role}) -{" "}
                {event.resource_type}
                {event.request_id ? ` - ${shortId(event.request_id)}` : ""}
              </small>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Dashboard({ data, loading, providerReachable, selectedProvider }) {
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
        <div className="hero-actions">
          <ProviderBadge provider={selectedProvider} />
          <span className={`status-pill ${status}`}>{status}</span>
        </div>
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

function ServersList({
  currentUser,
  loading,
  providerReachable,
  selectedProvider,
  servers,
  vmRequests,
  onAction,
}) {
  const [pendingServer, setPendingServer] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [selectedServer, setSelectedServer] = useState(null);

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
        <div className="hero-actions">
          <ProviderBadge provider={selectedProvider} />
          <RoleBadge user={currentUser} />
          <span className="status-pill">{servers.length} servers</span>
        </div>
      </div>

      <div className="requests-layout">
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
                  const failure = getFailureDetails(server);
                  const actionsAllowed =
                    providerReachable && canManageServer(server, currentUser, vmRequests);
                  return (
                    <tr className="clickable-row" key={server.id} onClick={() => setSelectedServer(server)}>
                      <td>
                        <strong>{server.name}</strong>
                        <small>{server.id}</small>
                      </td>
                      <td>
                        <span className={`server-status ${normalizeStatus(server.status)}`}>
                          {server.status ?? "unknown"}
                        </span>
                        {failure && (
                          <button
                            className="link-button error-link"
                            onClick={() => setSelectedServer(server)}
                            type="button"
                          >
                            View Error
                          </button>
                        )}
                      </td>
                      <td>{server.image_id ?? "-"}</td>
                      <td>{server.flavor_id ?? "-"}</td>
                      <td>{ips.privateIp ?? "-"}</td>
                      <td>{ips.floatingIp ?? "-"}</td>
                      <td onClick={(event) => event.stopPropagation()}>
                        <div className="button-row server-actions">
                        <ActionButton
                          busy={pendingServer === `${server.id}:start`}
                          disabled={!actionsAllowed}
                          label="Start"
                          onClick={() =>
                            runServerAction("start", "Start server", server, () =>
                              api.startServer(server.id),
                            )
                          }
                        />
                        <ActionButton
                          busy={pendingServer === `${server.id}:stop`}
                          disabled={!actionsAllowed}
                          label="Stop"
                          onClick={() =>
                            runServerAction("stop", "Stop server", server, () =>
                              api.stopServer(server.id),
                            )
                          }
                        />
                        <ActionButton
                          busy={pendingServer === `${server.id}:soft-reboot`}
                          disabled={!actionsAllowed}
                          label="Soft Reboot"
                          onClick={() =>
                            runServerAction("soft-reboot", "Soft reboot server", server, () =>
                              api.rebootServer(server.id),
                            )
                          }
                        />
                        <ActionButton
                          busy={pendingServer === `${server.id}:hard-reboot`}
                          disabled={!actionsAllowed}
                          label="Hard Reboot"
                          onClick={() =>
                            runServerAction("hard-reboot", "Hard reboot server", server, () =>
                              api.hardRebootServer(server.id),
                            )
                          }
                        />
                        <button
                          className="danger"
                          disabled={!actionsAllowed}
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

        <ServerDetailsPanel
          server={selectedServer}
          onClose={() => setSelectedServer(null)}
        />
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

function ServerDetailsPanel({ onClose, server }) {
  if (!server) {
    return (
      <aside className="request-details-panel empty-panel">
        <p className="eyebrow">Server</p>
        <h3>Select a server</h3>
        <p className="dashboard-copy">Click a server row to inspect its OpenStack details.</p>
      </aside>
    );
  }

  const ips = getServerIps(server.addresses);
  const failure = getFailureDetails(server);

  return (
    <aside className="request-details-panel server-details-panel">
      <div className="request-details-header">
        <div>
          <p className="eyebrow">Server</p>
          <h3>{server.name || shortId(server.id)}</h3>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </div>

      <dl className="request-result-details">
        <Detail label="Server ID" value={server.id} />
        <Detail label="Status" value={server.status} />
        <Detail label="VM state" value={server.vm_state} />
        <Detail label="Image" value={server.image_id} />
        <Detail label="Flavor" value={server.flavor_id} />
        <Detail label="Private IP" value={ips.privateIp} />
        <Detail label="Floating IP" value={ips.floatingIp} />
        <Detail label="Owner" value={server.metadata?.owner} />
        <Detail label="App tag" value={server.metadata?.app_tag} />
        <Detail label="Project" value={server.project_id} />
        <Detail label="Created" value={formatDateTime(server.created_at)} />
        <Detail label="Updated" value={formatDateTime(server.updated_at)} />
      </dl>

      {failure && <FailureNotice failure={failure} />}
      <JsonBlock title="Addresses" value={server.addresses} />
      <JsonBlock title="Raw Server Data" value={server} />
    </aside>
  );
}

function CreateVmForm({
  currentUser,
  images,
  flavors,
  initialValues,
  keypairs,
  networks,
  providerReachable,
  securityGroups,
  selectedProvider,
  onCreated,
  onError,
}) {
  const [form, setForm] = useState(emptyCreateForm);
  const [saving, setSaving] = useState(false);
  const [lastSubmission, setLastSubmission] = useState(null);
  const governance = evaluateGovernancePreview(form);
  const providerSelectionDisabled = !providerReachable && Boolean(form.catalog_service_name);
  const canSubmit = canManageResources(currentUser.role);

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
    if (name === "packages") {
      setForm((current) => {
        const packages = new Set(current.packages);
        if (checked) {
          packages.add(value);
        } else {
          packages.delete(value);
        }

        return { ...current, packages: Array.from(packages) };
      });
      return;
    }

    setForm((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!canSubmit) {
      onError("Not authorized: viewers cannot create VM requests.");
      return;
    }
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
        <div className="hero-actions">
          <ProviderBadge provider={selectedProvider} />
          <RoleBadge user={currentUser} />
        </div>
      </div>
      {!canSubmit && (
        <div className="alert warning">Not authorized: viewers cannot create VM requests.</div>
      )}
      <form className="form-grid" onSubmit={submit}>
        <section className="business-info-section">
          <h3>Business Information</h3>
          <div className="business-info-grid">
            <label>
              Project Name
              <input name="project_name" onChange={updateField} required value={form.project_name} />
            </label>
            <label>
              Cost Center
              <input name="cost_center" onChange={updateField} required value={form.cost_center} />
            </label>
            <label>
              Business Unit
              <input name="business_unit" onChange={updateField} value={form.business_unit} />
            </label>
            <label>
              Request Owner
              <input name="request_owner" onChange={updateField} required value={form.request_owner} />
            </label>
            <label>
              Team Name
              <input name="team_name" onChange={updateField} value={form.team_name} />
            </label>
          </div>
        </section>
        <section className="business-info-section">
          <h3>Application Information</h3>
          <div className="business-info-grid">
            <label>
              Application Name
              <input
                name="application_name"
                onChange={updateField}
                required
                value={form.application_name}
              />
            </label>
            <label>
              Application Type
              <select name="application_type" onChange={updateField} value={form.application_type}>
                {applicationTypeOptions.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>
            <label className="span-2">
              Purpose / Description
              <textarea
                name="purpose_description"
                onChange={updateField}
                rows={4}
                value={form.purpose_description}
              />
            </label>
          </div>
        </section>
        <section className="business-info-section">
          <h3>Environment &amp; Lifecycle</h3>
          <div className="business-info-grid">
            <label>
              Environment
              <select name="environment" onChange={updateField} required value={form.environment}>
                {environmentOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Lifetime
              <select name="lifetime" onChange={updateField} required value={form.lifetime}>
                {lifetimeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>
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
          App tag
          <input name="app_tag" onChange={updateField} required value={form.app_tag} />
        </label>
        <section className="business-info-section">
          <h3>Additional Packages</h3>
          <div className="package-checkbox-grid">
            {packageOptions.map((packageName) => (
              <label className="checkbox-label package-checkbox" key={packageName}>
                <input
                  checked={form.packages.includes(packageName)}
                  name="packages"
                  onChange={updateField}
                  type="checkbox"
                  value={packageName}
                />
                {packageName}
              </label>
            ))}
          </div>
        </section>
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
        <button className="primary form-submit" disabled={saving || !canSubmit} type="submit">
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
        <Detail label="Environment" value={formatEnvironment(result.request?.environment)} />
        <Detail label="Lifetime" value={formatLifetime(result.request)} />
        <Detail label="Expires at" value={formatDateTime(result.expires_at)} />
        <Detail label="Packages" value={formatPackages(result.request?.packages)} />
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

function FloatingIpsPanel({
  currentUser,
  floatingIps,
  providerReachable,
  servers,
  vmRequests,
  onAction,
}) {
  const [selectedServer, setSelectedServer] = useState("");
  const [selectedIp, setSelectedIp] = useState("");
  const actionsAllowed = providerReachable && canManageResources(currentUser.role);
  const manageableServers = servers.filter((server) => canManageServer(server, currentUser, vmRequests));

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
          disabled={!actionsAllowed}
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
          if (!actionsAllowed) {
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
          {manageableServers.map((server) => (
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
        <button disabled={!actionsAllowed} type="submit">
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
          <div>
            <strong>{toast.type === "error" ? "Action failed" : "Action completed"}</strong>
            <span>{toast.message}</span>
          </div>
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

function getFailureDetails(source) {
  if (!source) {
    return null;
  }

  if (source.failure_details) {
    return source.failure_details;
  }

  if (source.server?.failure_details) {
    return source.server.failure_details;
  }

  if (source.provisioning_error) {
    return {
      user_message: source.provisioning_error,
      suggested_action: "Review the request or try again after the provider issue is resolved.",
      technical_reason: source.provisioning_error,
      raw_error: null,
    };
  }

  return null;
}

function canAccessTab(tabId, role) {
  const tab = tabs.find((item) => item.id === tabId);
  return Boolean(tab?.roles.includes(role));
}

function canManageResources(role) {
  return role === "engineer" || role === "admin";
}

function canManageServer(server, user, requests) {
  if (user.role === "admin") {
    return true;
  }

  if (user.role !== "engineer") {
    return false;
  }

  const metadata = server.metadata ?? {};
  if (metadata.owner === user.name) {
    return true;
  }

  return requests.some((request) => {
    const requestPayload = request.request ?? {};
    const requestServer = request.server ?? {};
    const requestMetadata = requestServer.metadata ?? {};

    return (
      requestServer.id === server.id ||
      (requestServer.id === server.id && requestMetadata.owner === user.name) ||
      (metadata.app_tag && metadata.app_tag === requestPayload.app_tag)
    );
  });
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

function getRequestUser(request) {
  const payload = request?.request ?? {};
  return payload.request_owner || payload.requested_by || payload.user || payload.owner || payload.cost_center || "-";
}

function getRequestServiceName(request) {
  const payload = request?.request ?? {};
  return payload.catalog_service_name || payload.application_name || payload.app_tag || "-";
}

function normalizeEnvironmentValue(value) {
  const normalized = String(value || "").toLowerCase();
  const aliases = {
    dev: "Development",
    development: "Development",
    test: "Test",
    qa: "QA",
    stage: "UAT",
    staging: "UAT",
    uat: "UAT",
    prod: "Production",
    production: "Production",
  };

  return aliases[normalized] ?? "Development";
}

function formatEnvironment(value) {
  if (!value) {
    return "-";
  }

  return normalizeEnvironmentValue(value);
}

function getLifetimeDays(lifetime) {
  return lifetimeOptions.find((option) => option.value === lifetime)?.days ?? 30;
}

function formatLifetime(payload) {
  if (!payload) {
    return "-";
  }

  const selected = lifetimeOptions.find((option) => option.value === payload.lifetime);
  if (selected) {
    return selected.label;
  }

  const days = Number(payload.lifetime_days);
  if (days === 0) {
    return "Permanent";
  }

  return Number.isFinite(days) ? `${days} Day${days === 1 ? "" : "s"}` : "-";
}

function normalizePackageSelection(packages) {
  const values = Array.isArray(packages) ? packages : [];
  const aliases = new Map(
    packageOptions.map((packageName) => [
      packageName.toLowerCase().replaceAll(".", "").replaceAll("-", ""),
      packageName,
    ]),
  );
  aliases.set("nodejs", "Node.js");
  aliases.set("node", "Node.js");
  aliases.set("postgres", "PostgreSQL");
  aliases.set("postgresql", "PostgreSQL");
  aliases.set("mysql", "MySQL");

  return Array.from(new Set(values
    .map((item) => aliases.get(String(item).toLowerCase().replaceAll(".", "").replaceAll("-", "")))
    .filter(Boolean)));
}

function formatPackages(packages) {
  return Array.isArray(packages) && packages.length > 0 ? packages.join(", ") : "-";
}

function formatRequestedResources(payload) {
  if (!payload) {
    return "-";
  }

  return `${payload.cpu ?? "-"} vCPU / ${payload.ram_gb ?? "-"} GB RAM / ${payload.disk_gb ?? "-"} GB disk`;
}

function getCostBreakdown(request, policy = {}) {
  const cpu = Number(request?.cpu || 0) * 500;
  const ram = Number(request?.ram_gb || 0) * 150;
  const disk = Number(request?.disk_gb || 0) * 5;
  const calculatedTotal = cpu + ram + disk;
  const total = Number.isFinite(Number(policy.estimated_monthly_cost))
    ? Number(policy.estimated_monthly_cost)
    : calculatedTotal;

  return { cpu, ram, disk, total };
}

function buildGovernanceReasons(policy = {}, request = {}) {
  if (policy.reasons?.length > 0) {
    return policy.reasons.map((reason) => ({ label: reason, tone: "warning" }));
  }

  return [
    { label: "Cost within allowed budget", tone: "positive" },
    { label: "Compute within auto-approval limits", tone: "positive" },
    {
      label: request.public_ip_required ? "Public IP requested" : "Internal network only",
      tone: request.public_ip_required ? "warning" : "positive",
    },
    {
      label: request.catalog_service_name ? "Approved service template" : "Standard request",
      tone: "positive",
    },
  ];
}

function buildRequestTimeline(request) {
  const activity = request?.activity_log ?? [];
  const hasAction = (action) => activity.some((entry) => entry.action === action);
  const actionTime = (action) => activity.find((entry) => entry.action === action)?.created_at;
  const terminalTime = request?.updated_at !== request?.created_at ? request?.updated_at : null;

  return [
    {
      label: "Submitted",
      state: "done",
      time: request?.created_at,
      helper: "Request created",
    },
    {
      label: "Policy Evaluated",
      state: "done",
      time: request?.created_at,
      helper: "Governance score calculated",
    },
    {
      label: request?.status === "approval_required" ? "Awaiting Approval" : "Approval Decision",
      state:
        request?.status === "approval_required"
          ? "current"
          : ["approved", "rejected"].includes(request?.status)
            ? "done"
            : "skipped",
      time: ["approved", "rejected"].includes(request?.status) ? terminalTime : null,
      helper:
        request?.status === "approval_required"
          ? "Admin review required"
          : formatDecision(request?.status),
    },
    {
      label: "Provisioning",
      state:
        request?.server || hasAction("provisioned") || hasAction("approved")
          ? "done"
          : request?.status === "draft"
            ? "current"
            : "skipped",
      time: actionTime("provisioned") || actionTime("approved") || terminalTime,
      helper: request?.status === "draft" ? "Waiting for provider availability" : "VM creation",
    },
  ];
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
    environment: normalizeEnvironmentValue(service.environment),
    app_tag: service.app_tag,
    lifetime: "30_days",
    lifetime_days: "30",
    packages: normalizePackageSelection(service.packages),
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
    lifetime: form.lifetime,
    lifetime_days: getLifetimeDays(form.lifetime),
    packages: form.packages,
    public_ip_required: form.public_ip_required,
    project_name: form.project_name,
    business_unit: form.business_unit.trim() || null,
    request_owner: form.request_owner,
    team_name: form.team_name.trim() || null,
    application_name: form.application_name,
    application_type: form.application_type,
    purpose_description: form.purpose_description.trim() || null,
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
  const isProduction = environment === "production" || environment === "prod";
  const isPermanent = form.lifetime === "permanent" || getLifetimeDays(form.lifetime) === 0;
  const selectedPackages = new Set((form.packages || []).map((packageName) => packageName.toLowerCase()));
  const hasDatabasePackage = selectedPackages.has("postgresql") || selectedPackages.has("mysql");
  const hasPublicWebPackage =
    publicIpRequired && (selectedPackages.has("nginx") || selectedPackages.has("apache"));
  const catalogCost = Number(form.estimated_monthly_cost);
  const estimatedMonthlyCost = Number.isFinite(catalogCost) && catalogCost > 0
    ? catalogCost
    : cpu * 500 + ramGb * 150 + diskGb * 5;
  const reasons = [];

  const basicAutoApproved =
    cpu <= 6 &&
    ramGb <= 12 &&
    diskGb <= 200 &&
    !isProduction &&
    !publicIpRequired &&
    !isPermanent;

  let score = 0;

  if (estimatedMonthlyCost > 5000) {
    score += 30;
    reasons.push("Estimated monthly cost is greater than 5000");
  }

  if (publicIpRequired) {
    score += 30;
    reasons.push("Public IP requested");
  }

  if (isProduction) {
    score += 20;
    reasons.push("Production workload");
  }

  if (isPermanent) {
    score += 20;
    reasons.push("Permanent lifetime requested");
  }

  if (isCustomImage(form.image_id)) {
    score += 15;
    reasons.push("Custom image requested");
  }

  if (diskGb > 200) {
    score += 20;
    reasons.push("Disk size is greater than 200GB");
  }

  if (hasDatabasePackage) {
    score += 10;
    reasons.push("Database package selected");
  }

  if (hasPublicWebPackage) {
    score += 15;
    reasons.push("Web-facing package selected with public IP");
  }

  let governanceDecision =
    score <= 30 ? "auto_provision" : score <= 60 ? "auto_provision_notify" : "approval_required";

  if (isProduction && publicIpRequired) {
    governanceDecision = "approval_required";
    reasons.push("Production workloads with a public IP require approval");
  }

  if (isProduction && isPermanent) {
    governanceDecision = "approval_required";
    reasons.push("Permanent production workloads require approval");
  }
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
