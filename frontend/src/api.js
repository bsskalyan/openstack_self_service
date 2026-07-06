const API_BASE_URL = "http://10.161.230.18:8000/api/v1";
const USER_STORAGE_KEY = "cms-current-user";

let currentUser = {
  name: "Asha Engineer",
  role: "engineer",
};

try {
  const storedUser = window.localStorage.getItem(USER_STORAGE_KEY);
  if (storedUser) {
    currentUser = JSON.parse(storedUser);
  }
} catch {
  currentUser = {
    name: "Asha Engineer",
    role: "engineer",
  };
}

export function setApiUser(user) {
  currentUser = user;
  window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

export function buildSshConsoleWebSocketUrl(serverId) {
  const url = new URL(`${API_BASE_URL}/openstack/servers/${serverId}/ssh/ws`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("user", currentUser.name);
  url.searchParams.set("role", currentUser.role);
  return url.toString();
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-User-Name": currentUser.name,
      "X-User-Role": currentUser.role,
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.detail?.user_message) {
        message = payload.detail.user_message;
      } else {
        message = payload.detail?.technical_reason ?? message;
      }
    } catch {
      const text = await response.text();
      message = text || message;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  listProviders: () => request("/providers"),
  getOpenStackProviderConfig: () => request("/providers/openstack/config"),
  saveOpenStackProviderConfig: (payload) =>
    request("/providers/openstack/config", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  testOpenStackProviderConfig: (payload) =>
    request("/providers/openstack/test", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listCatalogServices: () => request("/catalog/services"),
  getStatus: () => request("/openstack/status"),
  listServers: () => request("/openstack/servers"),
  listImages: () => request("/openstack/images"),
  listFlavors: () => request("/openstack/flavors"),
  listNetworks: () => request("/openstack/networks"),
  listSecurityGroups: () => request("/openstack/security-groups"),
  listKeypairs: () => request("/openstack/keypairs"),
  listFloatingIps: () => request("/openstack/floating-ips"),
  createServer: (payload) =>
    request("/openstack/servers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  submitVmRequest: (payload) =>
    request("/openstack/requests", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listVmRequests: () => request("/openstack/requests"),
  getVmRequest: (requestId) => request(`/openstack/requests/${requestId}`),
  listAuditEvents: () => request("/openstack/audit"),
  getRequestTimeline: (requestId) => request(`/openstack/requests/${requestId}/timeline`),
  listPendingVmRequests: () => request("/openstack/requests/pending"),
  approveVmRequest: (requestId) =>
    request(`/openstack/requests/${requestId}/approve`, { method: "POST" }),
  rejectVmRequest: (requestId, reason) =>
    request(`/openstack/requests/${requestId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  startServer: (serverId) =>
    request(`/openstack/servers/${serverId}/start`, { method: "POST" }),
  stopServer: (serverId) =>
    request(`/openstack/servers/${serverId}/stop`, { method: "POST" }),
  rebootServer: (serverId) =>
    request(`/openstack/servers/${serverId}/reboot`, {
      method: "POST",
      body: JSON.stringify({ reboot_type: "SOFT" }),
    }),
  hardRebootServer: (serverId) =>
    request(`/openstack/servers/${serverId}/reboot`, {
      method: "POST",
      body: JSON.stringify({ reboot_type: "HARD" }),
    }),
  getServerConsole: (serverId) => request(`/openstack/servers/${serverId}/console`),
  getSshConsoleMetadata: (serverId) => request(`/openstack/servers/${serverId}/ssh-console`),
  listServerSnapshots: (serverId) => request(`/openstack/servers/${serverId}/snapshots`),
  createServerSnapshot: (serverId, payload) =>
    request(`/openstack/servers/${serverId}/snapshots`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteSnapshot: (snapshotId) =>
    request(`/openstack/snapshots/${snapshotId}`, { method: "DELETE" }),
  restoreSnapshot: (serverId, snapshotId, payload) =>
    request(`/openstack/servers/${serverId}/restore-snapshot/${snapshotId}`, {
      method: "POST",
      body: JSON.stringify(payload ?? { mode: "new_vm" }),
    }),
  deleteServer: (serverId) =>
    request(`/openstack/servers/${serverId}`, { method: "DELETE" }),
  createFloatingIp: () =>
    request("/openstack/floating-ips", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  attachFloatingIp: (serverId, floatingIp) =>
    request(`/openstack/servers/${serverId}/floating-ip`, {
      method: "POST",
      body: JSON.stringify({ floating_ip: floatingIp }),
    }),
};
