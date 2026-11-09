// ==========================================================
// AGRO FUTURE - Central API Client
// ==========================================================

const API = {
  // Base request wrapper
  async request(endpoint, options = {}) {
    const defaultHeaders = {
      "Content-Type": "application/json",
      "Accept": "application/json"
    };

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    };

    if (config.body && typeof config.body === "object") {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(endpoint, config);
      let data = {};
      try {
        data = await response.json();
      } catch (e) {
        // Fallback for non-JSON responses
      }
      if (!response.ok) {
        const msg = (typeof data.error === 'string' ? data.error : data.error?.message) || data.message || response.statusText || `HTTP error ${response.status}`;
        const err = new Error(msg);
        err.status = response.status;
        err.code = data.code;
        err.roles = data.roles;
        err.requested_role = data.requested_role;
        err.data = data;
        throw err;
      }
      return data;
    } catch (err) {
      console.error(`[API Error] ${endpoint}:`, err);
      throw err;
    }
  },

  // Auth endpoints
  auth: {
    getMe() {
      return API.request("/api/auth/me");
    },
    login(arg1, arg2, arg3) {
      let body;
      if (typeof arg1 === "object" && arg1 !== null) {
        body = arg1;
      } else {
        body = { email: arg1, password: arg2, role: arg3 };
      }
      return API.request("/api/auth/login", {
        method: "POST",
        body
      });
    },
    register(userData) {
      return API.request("/api/auth/register", {
        method: "POST",
        body: userData
      });
    },
    signupSendOtp(data) {
      return API.request("/api/auth/signup/send-otp", {
        method: "POST",
        body: data
      });
    },
    signupVerifyOtp(data) {
      return API.request("/api/auth/signup/verify-otp", {
        method: "POST",
        body: data
      });
    },
    adminLoginStep1(data) {
      return API.request("/api/auth/admin/verify-credentials", {
        method: "POST",
        body: data
      });
    },
    adminLoginStep2(data) {
      return API.request("/api/auth/admin/verify-otp", {
        method: "POST",
        body: data
      });
    },
    logout() {
      return API.request("/api/auth/logout", { method: "POST" });
    },
    forgotPasswordSendOtp(email) {
      return API.request("/api/auth/forgot-password/send-otp", {
        method: "POST",
        body: { email }
      });
    },
    forgotPasswordReset(data) {
      return API.request("/api/auth/forgot-password/reset", {
        method: "POST",
        body: data
      });
    },
    switchRole(role) {
      return API.request("/api/auth/switch-role", {
        method: "POST",
        body: { role }
      });
    },
    addRole(role, password) {
      return API.request("/api/auth/roles/add", {
        method: "POST",
        body: { role, password }
      });
    }
  },

  // Produce endpoints
  products: {
    list(params = {}) {
      const query = new URLSearchParams(params).toString();
      return API.request(`/api/products${query ? '?' + query : ''}`);
    },
    get(id) {
      return API.request(`/api/products/${id}`);
    },
    create(data) {
      return API.request("/api/products", {
        method: "POST",
        body: data
      });
    },
    update(id, data) {
      return API.request(`/api/products/${id}`, {
        method: "PUT",
        body: data
      });
    },
    delete(id) {
      return API.request(`/api/products/${id}`, {
        method: "DELETE"
      });
    }
  },

  // Machinery endpoints
  machinery: {
    list(params = {}) {
      const query = new URLSearchParams(params).toString();
      return API.request(`/api/machinery${query ? '?' + query : ''}`);
    },
    get(id) {
      return API.request(`/api/machinery/${id}`);
    },
    create(data) {
      return API.request("/api/machinery", {
        method: "POST",
        body: data
      });
    },
    update(id, data) {
      return API.request(`/api/machinery/${id}`, {
        method: "PUT",
        body: data
      });
    },
    delete(id) {
      return API.request(`/api/machinery/${id}`, {
        method: "DELETE"
      });
    }
  },

  // Orders endpoints
  orders: {
    create(orderData) {
      return API.request("/api/orders", {
        method: "POST",
        body: orderData
      });
    },
    list(params = {}) {
      const query = new URLSearchParams(params).toString();
      return API.request(`/api/orders${query ? '?' + query : ''}`);
    },
    updateStatus(orderId, status) {
      return API.request(`/api/orders/${orderId}/status`, {
        method: "PATCH",
        body: { status }
      });
    }
  },

  // Machinery Booking endpoints
  bookings: {
    create(bookingData) {
      return API.request("/api/bookings", {
        method: "POST",
        body: bookingData
      });
    },
    list(params = {}) {
      const query = new URLSearchParams(params).toString();
      return API.request(`/api/bookings${query ? '?' + query : ''}`);
    },
    updateStatus(bookingId, status) {
      return API.request(`/api/bookings/${bookingId}/status`, {
        method: "PATCH",
        body: { status }
      });
    }
  },

  // Super Admin endpoints
  admin: {
    getMetrics() {
      return API.request("/api/admin/metrics");
    },
    getCommissionSettings() {
      return API.request("/api/admin/commission-settings");
    },
    updateCommissionSettings(producePercent, machineryPercent) {
      return API.request("/api/admin/commission-settings", {
        method: "PUT",
        body: {
          produce_commission_percent: producePercent,
          machinery_commission_percent: machineryPercent
        }
      });
    },
    getUsers(role = "") {
      const query = role ? `?role=${role}` : "";
      return API.request(`/api/admin/users${query}`);
    },
    toggleUserStatus(userId, status) {
      return API.request(`/api/admin/users/${userId}/status`, {
        method: "PATCH",
        body: { status }
      });
    },
    getTransactions() {
      return API.request("/api/admin/transactions");
    }
  }
};
