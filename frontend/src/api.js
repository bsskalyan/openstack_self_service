const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail ?? message;
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
