// ==========================================================
// AGRO FUTURE - Master Frontend Logic & Multi-Panel Manager
// ==========================================================

const AppState = {
  currentUser: null,
  currentRole: "landing",       // starts on landing page
  cart: [],
  produceFilter: "all",
  machineryFilter: "all",
  activeCustomerSubTab: "produce",
  activeFarmerSubTab: "produce",
  activeSellerSubTab: "fleet",
  activeAdminSubTab: "overview",
  currentBookingMachinery: null
};

// ===================================================================
// AUTH STATE  — tracks who is logged in to which panel
// ===================================================================
const AuthState = {
  // Each panel has its own login session (email/name + role)
  sessions: {
    customer: null,
    farmer: null,
    machinery_seller: null,
    super_admin: null
  },
  // Admin credentials (hardcoded)
  ADMIN_USERNAME: "Agrofuture",
  ADMIN_PASSWORD: "agrofuture@1540"
};

// ===================================================================
// AUTH MODAL HELPERS
// ===================================================================
function openAuthModal(role) {
  const modal = document.getElementById(`authModal-${role}`);
  if (modal) {
    // Reset errors & inputs
    const errEl = document.getElementById(`authError-${role}`);
    if (errEl) { errEl.style.display = "none"; errEl.textContent = ""; }
    modal.classList.add("active");
  }
}

function closeAuthModal(role) {
  const modal = document.getElementById(`authModal-${role}`);
  if (modal) modal.classList.remove("active");
}

// Close auth modal when clicking overlay background
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("auth-modal-overlay")) {
    e.target.classList.remove("active");
  }
});

// ===================================================================
// REQUEST PANEL ACCESS — called by all panel buttons & landing cards
// ===================================================================
function requestPanelAccess(role) {
  // If already logged in for this panel, just switch to it
  if (AuthState.sessions[role]) {
    switchToPanel(role);
    return;
  }
  // Otherwise open the login modal
  openAuthModal(role);
}

// ===================================================================
// PANEL SWITCH (post-auth)
// ===================================================================
function switchToPanel(role) {
  AppState.currentRole = role;

  // Hide all panels
  document.querySelectorAll(".panel-view").forEach(el => el.classList.remove("active"));

  // Show the target panel
  const panelEl = document.getElementById(`panel-${role}`);
  if (panelEl) panelEl.classList.add("active");

  // Update top-bar button states
  updateTopBarState(role);

  // Load panel data
  if (role === "customer") loadCustomerData();
  else if (role === "farmer") loadFarmerData();
  else if (role === "machinery_seller") loadSellerData();
  else if (role === "super_admin") loadAdminData();
}

function updateTopBarState(activeRole) {
  // Update role buttons active/locked/unlocked state
  document.querySelectorAll(".role-btn[data-role]").forEach(btn => {
    const r = btn.dataset.role;
    btn.classList.remove("active", "locked", "unlocked");
    if (r === activeRole) {
      btn.classList.add("active");
    } else if (AuthState.sessions[r]) {
      btn.classList.add("unlocked");
    } else {
      btn.classList.add("locked");
    }
  });

  // Show/hide logout button and update label
  const logoutBtn = document.getElementById("globalLogoutBtn");
  const labelEl   = document.getElementById("panelBarLabel");
  const session   = AuthState.sessions[activeRole];

  if (activeRole !== "landing" && session) {
    if (logoutBtn) logoutBtn.style.display = "";
    const panelNames = { customer: "User", farmer: "Farmer", machinery_seller: "Seller", super_admin: "Admin" };
    if (labelEl) labelEl.textContent = `${panelNames[activeRole] || ""} Panel — Signed in as ${session.name}`;
  } else {
    if (logoutBtn) logoutBtn.style.display = "none";
    if (labelEl) labelEl.textContent = "SELECT YOUR PANEL:";
  }

  // Update header user display
  if (session) {
    const nameEl = document.getElementById("headerUserName");
    const roleEl = document.getElementById("headerUserRole");
    if (nameEl) nameEl.textContent = session.name;
    if (roleEl) roleEl.textContent = formatRole(activeRole);
  }
}

// ===================================================================
// LOGOUT
// ===================================================================
function logoutCurrentPanel() {
  const role = AppState.currentRole;
  if (role && role !== "landing") {
    AuthState.sessions[role] = null;
    showToast(`Signed out of ${formatRole(role)} panel`, "info");
  }
  // Return to landing
  AppState.currentRole = "landing";
  document.querySelectorAll(".panel-view").forEach(el => el.classList.remove("active"));
  const landingEl = document.getElementById("panel-landing");
  if (landingEl) landingEl.classList.add("active");
  updateTopBarState("landing");
}

// ===================================================================
// HANDLE LOGIN: Customer / Farmer / Seller panels
// ===================================================================
async function handlePanelLogin(event, role) {
  event.preventDefault();

  const emailEl    = document.getElementById(`authEmail-${role}`);
  const passwordEl = document.getElementById(`authPassword-${role}`);
  const errEl      = document.getElementById(`authError-${role}`);

  const email    = emailEl ? emailEl.value.trim() : "";
  const password = passwordEl ? passwordEl.value : "";

  if (!email || !password) {
    showAuthError(role, "Please enter your email and password.");
    return;
  }

  // Basic email validation — must be a valid email (Gmail encouraged but any email works)
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showAuthError(role, "Please enter a valid email address.");
    return;
  }

  try {
    // Try backend auth if available; fall back to accepting any valid email+password
    let userName = email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    try {
      const res = await API.auth.login({ email, password, role });
      if (res && res.user) {
        userName = res.user.full_name || userName;
      }
    } catch (apiErr) {
      // Backend auth not available — accept any email/password as valid for demo
      if (password.length < 6) {
        showAuthError(role, "Password must be at least 6 characters.");
        return;
      }
    }

    // Grant access
    AuthState.sessions[role] = { email, name: userName, loginTime: new Date() };
    closeAuthModal(role);
    showToast(`✅ Signed in as ${userName} — Welcome to ${formatRole(role)} panel!`, "success");
    switchToPanel(role);

  } catch (err) {
    showAuthError(role, err.message || "Login failed. Please check your credentials.");
  }
}

// ===================================================================
// HANDLE LOGIN: Admin Panel (hardcoded credentials)
// ===================================================================
function handleAdminLogin(event) {
  event.preventDefault();

  const usernameEl = document.getElementById("adminUsername");
  const passwordEl = document.getElementById("adminPassword");

  const username = usernameEl ? usernameEl.value.trim() : "";
  const password = passwordEl ? passwordEl.value : "";

  if (!username || !password) {
    showAuthError("super_admin", "Please enter username and password.");
    return;
  }

  // Strict hardcoded credential check (case-sensitive)
  if (username === AuthState.ADMIN_USERNAME && password === AuthState.ADMIN_PASSWORD) {
    AuthState.sessions["super_admin"] = { email: "admin@agrofuture.in", name: "Agrofuture Admin", loginTime: new Date() };
    closeAuthModal("super_admin");

    // Clear inputs for security
    if (usernameEl) usernameEl.value = "";
    if (passwordEl) passwordEl.value = "";

    showToast("✅ Admin access granted — Welcome, Agrofuture Admin!", "success");
    switchToPanel("super_admin");
  } else {
    showAuthError("super_admin", "❌ Invalid credentials. Access denied.");
    // Shake the form for visual feedback
    const box = document.querySelector("#authModal-super_admin .auth-modal-box");
    if (box) {
      box.style.animation = "none";
      box.offsetHeight; // reflow
      box.style.animation = "authShake 0.4s ease";
    }
  }
}

// ===================================================================
// HANDLE GOOGLE SIGN-IN (simulated — opens Gmail prompt)
// ===================================================================
function handleGoogleSignIn(role) {
  // Since no Google Client ID is configured, simulate with a simple prompt
  // In production: integrate Google Identity Services SDK with a real Client ID
  const email = prompt(
    `🔵 Google Sign-In for ${formatRole(role)} Panel\n\nEnter your Gmail address to continue:`,
    ""
  );
  if (!email) return;

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showAuthError(role, "Please enter a valid Gmail address.");
    return;
  }

  const name = email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  AuthState.sessions[role] = { email, name, loginTime: new Date(), via: "google" };
  closeAuthModal(role);
  showToast(`✅ Signed in with Google as ${name}!`, "success");
  switchToPanel(role);
}

// ===================================================================
// AUTH ERROR DISPLAY
// ===================================================================
function showAuthError(role, message) {
  const errEl = document.getElementById(`authError-${role}`);
  if (errEl) {
    errEl.textContent = message;
    errEl.style.display = "block";
  }
}

// ===================================================================
// PASSWORD EYE TOGGLE
// ===================================================================
function toggleAuthPassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === "password") {
    input.type = "text";
    btn.textContent = "🙈";
  } else {
    input.type = "password";
    btn.textContent = "👁️";
  }
}

// Add shake keyframe for admin wrong password
(function() {
  const style = document.createElement("style");
  style.textContent = `@keyframes authShake {
    0%,100%{transform:translateX(0)}
    20%{transform:translateX(-8px)}
    40%{transform:translateX(8px)}
    60%{transform:translateX(-6px)}
    80%{transform:translateX(6px)}
  }`;
  document.head.appendChild(style);
})();

// ================= INITIALIZATION =================
document.addEventListener("DOMContentLoaded", async () => {
  initCartFromStorage();
  // Start on landing page — do NOT auto-load user or panel
  AppState.currentRole = "landing";
  updateTopBarState("landing");
  // Mark all panel buttons as locked initially
  document.querySelectorAll(".role-btn[data-role]").forEach(btn => {
    btn.classList.add("locked");
  });
  setupEventListeners();
});


// ================= AUTH & PERSPECTIVE SWITCHING =================
async function loadCurrentUser() {
  try {
    const res = await API.auth.getMe();
    if (res.user) {
      AppState.currentUser = res.user;
      AppState.currentRole = res.user.role;
      updateHeaderUserUI();
    }
  } catch (err) {
    console.error("Error fetching user:", err);
  }
}

function updateHeaderUserUI() {
  const nameEl = document.getElementById("headerUserName");
  const roleEl = document.getElementById("headerUserRole");
  const avatarEl = document.getElementById("headerUserAvatar");

  if (AppState.currentUser) {
    if (nameEl) nameEl.textContent = AppState.currentUser.full_name;
    if (roleEl) roleEl.textContent = formatRole(AppState.currentUser.role);
    if (avatarEl && AppState.currentUser.avatar_url) {
      avatarEl.src = AppState.currentUser.avatar_url;
    }
  }

  // Update active pill button in top demo bar
  document.querySelectorAll(".role-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.role === AppState.currentRole);
  });
}

function formatRole(role) {
  switch (role) {
    case "super_admin": return "Super Admin";
    case "farmer": return "Farmer";
    case "machinery_seller": return "Machinery Seller";
    case "customer": return "Customer";
    default: return role;
  }
}

async function switchPerspective(role) {
  // Redirect to the new auth-gated access system
  requestPanelAccess(role);
}

// ================= PANEL ROUTER =================
function renderCurrentPanel() {
  // Hide all panels
  document.querySelectorAll(".panel-view").forEach(el => el.classList.remove("active"));

  const role = AppState.currentRole;

  // Show active panel (including landing)
  const panelId = `panel-${role}`;
  const panelEl = document.getElementById(panelId);
  if (panelEl) {
    panelEl.classList.add("active");
  }

  // Load panel specific data (only if authenticated)
  if (role === "customer" && AuthState.sessions.customer) {
    loadCustomerData();
  } else if (role === "farmer" && AuthState.sessions.farmer) {
    loadFarmerData();
  } else if (role === "machinery_seller" && AuthState.sessions.machinery_seller) {
    loadSellerData();
  } else if (role === "super_admin" && AuthState.sessions.super_admin) {
    loadAdminData();
  }
}


// ================= CUSTOMER PANEL LOGIC =================
async function loadCustomerData() {
  if (AppState.activeCustomerSubTab === "produce") {
    await loadProduceCatalog();
  } else if (AppState.activeCustomerSubTab === "machinery") {
    await loadMachineryCatalog();
  } else if (AppState.activeCustomerSubTab === "my-orders") {
    await loadCustomerOrders();
  } else if (AppState.activeCustomerSubTab === "my-bookings") {
    await loadCustomerBookings();
  }
}

async function loadProduceCatalog() {
  const container = document.getElementById("produceGrid");
  if (!container) return;
  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">Loading fresh produce...</div>`;

  try {
    const searchVal = document.getElementById("produceSearch") ? document.getElementById("produceSearch").value.trim() : "";
    const res = await API.products.list({
      category: AppState.produceFilter,
      search: searchVal,
      status: "active"
    });

    if (!res.products || res.products.length === 0) {
      container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted); background: white; border-radius: var(--radius-md); border: 1px dashed var(--border-light);">No produce items match your search. Try another category or keyword.</div>`;
      return;
    }

    container.innerHTML = res.products.map(p => {
      const isOrganic = p.is_organic == 1 || p.is_organic === true;
      const inStock = p.stock_quantity > 0;
      return `
        <div class="product-card">
          <div class="card-img-wrap">
            <img src="${p.image_url || 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=600'}" alt="${p.title}" class="card-img" loading="lazy">
            <div class="card-badges">
              <span class="badge badge-category">${p.category}</span>
              ${isOrganic ? '<span class="badge badge-organic">🌿 100% Organic</span>' : ''}
            </div>
          </div>
          <div class="card-body">
            <h3 class="card-title">${p.title}</h3>
            <p class="card-subtitle">Farmer: ${p.farmer_name || 'Verified Agro Grower'} • ${p.farmer_location || 'Local'}</p>
            <p class="card-desc">${p.description || p.variety || 'Freshly harvested produce directly from farm to table.'}</p>
            <div class="card-pricing-row">
              <div class="price-box">
                <span class="price-main">₹${parseFloat(p.price_per_unit).toFixed(2)}</span>
                <span class="price-unit">per ${p.unit}</span>
              </div>
              <div class="stock-indicator ${inStock ? '' : 'stock-out'}">
                ${inStock ? `In Stock (${p.stock_quantity} ${p.unit}s)` : 'Out of Stock'}
              </div>
            </div>
            ${inStock ? `
              <div class="card-actions">
                <div class="qty-stepper">
                  <button type="button" class="qty-btn" onclick="stepProduceQty('${p.id}', -1)">-</button>
                  <span class="qty-val" id="qty-${p.id}">1</span>
                  <button type="button" class="qty-btn" onclick="stepProduceQty('${p.id}', 1)">+</button>
                </div>
                <button type="button" class="btn-add-cart" onclick="addToCart('${p.id}', '${escapeHtml(p.title)}', ${p.price_per_unit}, '${p.unit}', '${p.image_url}', '${p.farmer_id}')">
                  🛒 Add to Cart
                </button>
              </div>
            ` : `
              <button type="button" class="btn-secondary" style="width: 100%;" disabled>Out of Stock</button>
            `}
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: #dc2626; padding: 20px;">Failed to load produce: ${err.message}</div>`;
  }
}

function stepProduceQty(productId, delta) {
  const el = document.getElementById(`qty-${productId}`);
  if (!el) return;
  let val = parseInt(el.textContent) || 1;
  val = Math.max(1, val + delta);
  el.textContent = val;
}

// Machinery Catalog
async function loadMachineryCatalog() {
  const container = document.getElementById("machineryGrid");
  if (!container) return;
  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">Loading agricultural machinery...</div>`;

  try {
    const searchVal = document.getElementById("machinerySearch") ? document.getElementById("machinerySearch").value.trim() : "";
    const res = await API.machinery.list({
      category: AppState.machineryFilter,
      search: searchVal
    });

    if (!res.machinery || res.machinery.length === 0) {
      container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted); background: white; border-radius: var(--radius-md); border: 1px dashed var(--border-light);">No machinery available in this category.</div>`;
      return;
    }

    container.innerHTML = res.machinery.map(m => {
      const isAvailable = m.is_available == 1 || m.is_available === true;
      const hasOperator = m.includes_operator == 1 || m.includes_operator === true;
      return `
        <div class="machinery-card">
          <div class="card-img-wrap">
            <img src="${m.image_url || 'https://images.unsplash.com/photo-1592878904946-b3cd8ae243d0?w=600'}" alt="${m.title}" class="card-img" loading="lazy">
            <div class="card-badges">
              <span class="badge badge-category">${formatMachineryCategory(m.category)}</span>
              <span class="badge ${isAvailable ? 'badge-available' : 'badge-unavailable'}">
                ${isAvailable ? '● Ready for Hire' : '○ In Maintenance'}
              </span>
            </div>
          </div>
          <div class="card-body">
            <h3 class="card-title">${m.title}</h3>
            <p class="card-subtitle">Seller: ${m.seller_name || 'Agro Machinery Hub'} • ${m.location || 'Local'}</p>
            <p class="card-desc">${m.specifications || m.model_info || 'High performance farming machinery for efficient cultivation.'}</p>
            
            <div class="card-specs">
              <div class="spec-item">⚙️ Model: ${m.model_info || 'Standard'}</div>
              <div class="spec-item">👨‍🔧 Operator: ${hasOperator ? `Available (+₹${m.operator_charge_per_hour}/hr)` : 'Self-drive'}</div>
            </div>

            <div class="card-pricing-row">
              <div class="price-box">
                <span class="price-main">₹${parseFloat(m.hourly_rate).toFixed(0)} <span style="font-size: 0.8rem; font-weight: 500;">/hr</span></span>
                <span class="price-unit">or ₹${parseFloat(m.daily_rate).toFixed(0)} /day</span>
              </div>
            </div>

            ${isAvailable ? `
              <button type="button" class="btn-book-rental" onclick="openBookingModal('${m.id}')">
                🚜 Book Rental
              </button>
            ` : `
              <button type="button" class="btn-secondary" style="width: 100%;" disabled>Currently Unavailable</button>
            `}
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: #dc2626; padding: 20px;">Failed to load machinery: ${err.message}</div>`;
  }
}

function formatMachineryCategory(cat) {
  const map = {
    tractor: "Tractor",
    harvester: "Harvester",
    water_pump: "Water Pump",
    bulldozer: "Bulldozer",
    power_tiller: "Power Tiller",
    sprayer: "Sprayer"
  };
  return map[cat] || cat;
}

// Machinery Booking Modal & Live Calculator
async function openBookingModal(machineryId) {
  try {
    const res = await API.machinery.get(machineryId);
    const m = res.machinery;
    AppState.currentBookingMachinery = m;

    document.getElementById("modalMachineryTitle").textContent = m.title;
    document.getElementById("modalMachineryImage").src = m.image_url;
    document.getElementById("modalMachineryRates").innerHTML = `
      <strong>Rates:</strong> ₹${m.hourly_rate}/hour | ₹${m.daily_rate}/day 
      ${m.includes_operator ? `<br><span style="color: var(--primary); font-size: 0.82rem;">👨‍🔧 Professional Operator Available (+₹${m.operator_charge_per_hour}/hr)</span>` : ''}
    `;

    // Operator checkbox toggle
    const opGroup = document.getElementById("modalOperatorGroup");
    const opCheck = document.getElementById("bookingOperatorCheck");
    if (m.includes_operator) {
      opGroup.style.display = "flex";
      opCheck.checked = false;
    } else {
      opGroup.style.display = "none";
      opCheck.checked = false;
    }

    // Set default start datetime to tomorrow 9am
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    const dateStr = tomorrow.toISOString().slice(0, 16);
    document.getElementById("bookingStartDateTime").value = dateStr;

    calculateBookingTotal();
    openModal("bookingModal");
  } catch (err) {
    showToast(`Error opening booking modal: ${err.message}`, "error");
  }
}

function calculateBookingTotal() {
  const m = AppState.currentBookingMachinery;
  if (!m) return;

  const type = document.getElementById("bookingRentalType").value;
  const duration = parseFloat(document.getElementById("bookingDuration").value) || 1;
  const withOp = document.getElementById("bookingOperatorCheck").checked;

  let baseRate = type === "hourly" ? parseFloat(m.hourly_rate) : parseFloat(m.daily_rate);
  let baseCost = baseRate * duration;
  let opFee = 0;

  if (withOp && m.includes_operator) {
    const opRatePerHour = parseFloat(m.operator_charge_per_hour || 0);
    opFee = type === "hourly" ? opRatePerHour * duration : (opRatePerHour * 8) * duration;
  }

  const grandTotal = baseCost + opFee;

  document.getElementById("bookingDurationLabel").textContent = type === "hourly" ? "Duration (Hours)" : "Duration (Days)";
  document.getElementById("bookingTotalDisplay").innerHTML = `
    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: var(--text-muted); margin-bottom: 4px;">
      <span>Rental Base (${duration} ${type === 'hourly' ? 'hrs' : 'days'} @ ₹${baseRate}):</span>
      <span>₹${baseCost.toFixed(2)}</span>
    </div>
    ${opFee > 0 ? `
      <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: var(--primary); margin-bottom: 4px;">
        <span>Operator Services:</span>
        <span>₹${opFee.toFixed(2)}</span>
      </div>
    ` : ''}
    <div style="display: flex; justify-content: space-between; font-size: 1.15rem; font-weight: 800; color: var(--text-main); border-top: 1px dashed var(--border-light); padding-top: 8px; margin-top: 6px;">
      <span>Total Estimated Rental:</span>
      <span style="color: var(--primary);">₹${grandTotal.toFixed(2)}</span>
    </div>
  `;
}

async function submitMachineryBooking(e) {
  e.preventDefault();
  const m = AppState.currentBookingMachinery;
  if (!m) return;

  const rentalType = document.getElementById("bookingRentalType").value;
  const duration = parseFloat(document.getElementById("bookingDuration").value) || 1;
  const startDateTime = document.getElementById("bookingStartDateTime").value;
  const withOperator = document.getElementById("bookingOperatorCheck").checked;
  const location = document.getElementById("bookingDeliveryLocation").value.trim();
  const notes = document.getElementById("bookingNotes").value.trim();

  if (!location) {
    showToast("Please enter the delivery farm / site location.", "error");
    return;
  }

  try {
    const res = await API.bookings.create({
      machinery_id: m.id,
      rental_type: rentalType,
      duration_units: duration,
      start_datetime: startDateTime,
      with_operator: withOperator,
      delivery_location: location,
      notes: notes
    });

    closeModal("bookingModal");
    showToast(res.message, "info");
    // Switch to Customer My Bookings tab to show the placed booking
    setCustomerSubTab("my-bookings");
  } catch (err) {
    showToast(`Booking failed: ${err.message}`, "error");
  }
}

// Customer Orders & Bookings view
async function loadCustomerOrders() {
  const container = document.getElementById("customerOrdersTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading your orders...</td></tr>`;

  try {
    const res = await API.orders.list({ role: "customer" });
    if (!res.orders || res.orders.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">You have no active orders yet. Browse our produce marketplace to order fresh farm harvest!</td></tr>`;
      return;
    }

    container.innerHTML = res.orders.map(o => {
      const itemsSummary = (o.items || []).map(i => `${i.product_title} (${i.quantity} ${i.unit || 'kg'})`).join(", ");
      return `
        <tr>
          <td><strong>${o.order_number}</strong></td>
          <td>${formatDateTime(o.created_at)}</td>
          <td>${itemsSummary || 'Produce items'}</td>
          <td><strong>₹${parseFloat(o.total_amount).toFixed(2)}</strong></td>
          <td>${o.shipping_address}</td>
          <td><span class="status-pill status-${o.status}">${o.status}</span></td>
          <td>${o.payment_method ? o.payment_method.toUpperCase() : 'COD'}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load orders: ${err.message}</td></tr>`;
  }
}

async function loadCustomerBookings() {
  const container = document.getElementById("customerBookingsTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading your machinery bookings...</td></tr>`;

  try {
    const res = await API.bookings.list({ role: "customer" });
    if (!res.bookings || res.bookings.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">No machinery bookings found. Browse tractors, harvesters, and pumps in the Machinery Rental tab!</td></tr>`;
      return;
    }

    container.innerHTML = res.bookings.map(b => {
      return `
        <tr>
          <td><strong>${b.booking_number}</strong></td>
          <td>
            <strong>${b.machinery_title || 'Agricultural Machine'}</strong>
            <br><span style="font-size: 0.75rem; color: var(--text-muted);">${formatMachineryCategory(b.machinery_category)}</span>
          </td>
          <td>${b.duration_units} ${b.rental_type === 'hourly' ? 'Hours' : 'Days'} ${b.with_operator ? '(With Operator)' : ''}</td>
          <td>${formatDateTime(b.start_datetime)}</td>
          <td><strong>₹${parseFloat(b.total_amount).toFixed(2)}</strong></td>
          <td>${b.delivery_location}</td>
          <td><span class="status-pill status-${b.status}">${b.status}</span></td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load bookings: ${err.message}</td></tr>`;
  }
}

// ================= SHOPPING CART LOGIC =================
function initCartFromStorage() {
  try {
    const saved = localStorage.getItem("agro_future_cart");
    if (saved) {
      AppState.cart = JSON.parse(saved);
      updateCartBadge();
    }
  } catch (e) {
    AppState.cart = [];
  }
}

function saveCartToStorage() {
  try {
    localStorage.setItem("agro_future_cart", JSON.stringify(AppState.cart));
  } catch (e) {}
  updateCartBadge();
}

function updateCartBadge() {
  const count = AppState.cart.reduce((sum, item) => sum + item.quantity, 0);
  const badges = document.querySelectorAll(".cart-badge");
  badges.forEach(b => {
    b.textContent = count;
    b.style.display = count > 0 ? "inline-flex" : "none";
  });
}

function addToCart(productId, title, price, unit, image, farmerId) {
  const qtyEl = document.getElementById(`qty-${productId}`);
  const qty = qtyEl ? parseInt(qtyEl.textContent) || 1 : 1;

  const existing = AppState.cart.find(item => item.product_id === productId);
  if (existing) {
    existing.quantity += qty;
  } else {
    AppState.cart.push({
      product_id: productId,
      title: title,
      price: price,
      unit: unit,
      image_url: image,
      farmer_id: farmerId,
      quantity: qty
    });
  }

  saveCartToStorage();
  showToast(`Added ${qty} ${unit} of "${title}" to your cart!`, "info");
  renderCartDrawer();
}

function updateCartItemQty(productId, delta) {
  const item = AppState.cart.find(i => i.product_id === productId);
  if (!item) return;

  item.quantity += delta;
  if (item.quantity <= 0) {
    AppState.cart = AppState.cart.filter(i => i.product_id !== productId);
  }

  saveCartToStorage();
  renderCartDrawer();
}

function renderCartDrawer() {
  const container = document.getElementById("cartItemsContainer");
  const subtotalEl = document.getElementById("cartSubtotal");
  const totalEl = document.getElementById("cartGrandTotal");
  if (!container) return;

  if (AppState.cart.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
        <div style="font-size: 3rem; margin-bottom: 12px;">🛒</div>
        <p style="font-weight: 600;">Your cart is empty.</p>
        <p style="font-size: 0.85rem; margin-top: 4px;">Explore fresh fruits, vegetables, and greens from our local farmers.</p>
      </div>
    `;
    if (subtotalEl) subtotalEl.textContent = "₹0.00";
    if (totalEl) totalEl.textContent = "₹0.00";
    return;
  }

  let subtotal = 0;
  container.innerHTML = AppState.cart.map(item => {
    const itemTotal = item.price * item.quantity;
    subtotal += itemTotal;
    return `
      <div class="cart-item-card">
        <img src="${item.image_url || 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=150'}" alt="${item.title}" class="cart-item-img">
        <div class="cart-item-info">
          <div class="cart-item-title">${item.title}</div>
          <div class="cart-item-price">₹${parseFloat(item.price).toFixed(2)} / ${item.unit}</div>
          <div style="font-weight: 700; color: var(--text-main); font-size: 0.85rem; margin-top: 2px;">Total: ₹${itemTotal.toFixed(2)}</div>
        </div>
        <div class="qty-stepper">
          <button type="button" class="qty-btn" onclick="updateCartItemQty('${item.product_id}', -1)">-</button>
          <span class="qty-val">${item.quantity}</span>
          <button type="button" class="qty-btn" onclick="updateCartItemQty('${item.product_id}', 1)">+</button>
        </div>
      </div>
    `;
  }).join("");

  if (subtotalEl) subtotalEl.textContent = `₹${subtotal.toFixed(2)}`;
  if (totalEl) totalEl.textContent = `₹${subtotal.toFixed(2)}`;
}

function openCart() {
  renderCartDrawer();
  document.getElementById("cartDrawerOverlay").classList.add("open");
  document.getElementById("cartDrawer").classList.add("open");
}

function closeCart() {
  document.getElementById("cartDrawerOverlay").classList.remove("open");
  document.getElementById("cartDrawer").classList.remove("open");
}

async function proceedToCheckout() {
  if (AppState.cart.length === 0) {
    showToast("Your cart is empty!", "error");
    return;
  }

  closeCart();
  // Open checkout modal
  const summaryEl = document.getElementById("checkoutItemsSummary");
  let subtotal = 0;
  summaryEl.innerHTML = AppState.cart.map(i => {
    const t = i.price * i.quantity;
    subtotal += t;
    return `<div style="display: flex; justify-content: space-between; font-size: 0.85rem; padding: 4px 0;">
      <span>${i.title} (${i.quantity} ${i.unit})</span>
      <strong>₹${t.toFixed(2)}</strong>
    </div>`;
  }).join("");

  document.getElementById("checkoutTotalDisplay").textContent = `₹${subtotal.toFixed(2)}`;
  openModal("checkoutModal");
}

async function submitOrder(e) {
  e.preventDefault();
  const address = document.getElementById("checkoutAddress").value.trim();
  const phone = document.getElementById("checkoutPhone").value.trim();
  const paymentMethod = document.getElementById("checkoutPaymentMethod").value;

  if (!address || !phone) {
    showToast("Please provide delivery address and contact phone.", "error");
    return;
  }

  try {
    const res = await API.orders.create({
      items: AppState.cart.map(i => ({ product_id: i.product_id, quantity: i.quantity })),
      shipping_address: address,
      contact_phone: phone,
      payment_method: paymentMethod
    });

    // Clear cart
    AppState.cart = [];
    saveCartToStorage();
    closeModal("checkoutModal");
    showToast(res.message, "info");

    // Switch to My Orders tab
    setCustomerSubTab("my-orders");
  } catch (err) {
    showToast(`Order failed: ${err.message}`, "error");
  }
}

// ================= FARMER PANEL LOGIC =================
async function loadFarmerData() {
  await loadFarmerMetrics();
  if (AppState.activeFarmerSubTab === "produce") {
    await loadFarmerProduceList();
  } else if (AppState.activeFarmerSubTab === "orders") {
    await loadFarmerOrdersList();
  } else if (AppState.activeFarmerSubTab === "earnings") {
    await loadFarmerEarnings();
  }
}

async function loadFarmerMetrics() {
  try {
    const prodRes = await API.products.list({ farmer_id: AppState.currentUser ? AppState.currentUser.id : "" });
    const orderRes = await API.orders.list({ role: "farmer" });

    const totalListings = prodRes.products ? prodRes.products.length : 0;
    const orders = orderRes.orders || [];
    
    let grossSales = 0;
    let netEarnings = 0;
    let totalOrders = orders.length;

    orders.forEach(o => {
      if (o.farmer_items) {
        o.farmer_items.forEach(it => {
          grossSales += it.subtotal || 0;
          netEarnings += it.farmer_earnings || 0;
        });
      }
    });

    const commPaid = grossSales - netEarnings;

    document.getElementById("farmerStatListings").textContent = totalListings;
    document.getElementById("farmerStatOrders").textContent = totalOrders;
    document.getElementById("farmerStatGrossSales").textContent = `₹${grossSales.toFixed(2)}`;
    document.getElementById("farmerStatNetEarnings").textContent = `₹${netEarnings.toFixed(2)}`;
    document.getElementById("farmerStatCommission").textContent = `₹${commPaid.toFixed(2)} (Platform 5%)`;
  } catch (err) {
    console.error("Failed to load farmer metrics:", err);
  }
}

async function loadFarmerProduceList() {
  const container = document.getElementById("farmerProduceTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading your produce listings...</td></tr>`;

  try {
    const res = await API.products.list({ farmer_id: AppState.currentUser ? AppState.currentUser.id : "" });
    if (!res.products || res.products.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">No produce listed yet. Click "+ Add Produce" to list your harvest!</td></tr>`;
      return;
    }

    container.innerHTML = res.products.map(p => {
      const inStock = p.stock_quantity > 0;
      return `
        <tr>
          <td>
            <div style="display: flex; align-items: center; gap: 10px;">
              <img src="${p.image_url || 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=100'}" style="width: 44px; height: 44px; border-radius: 6px; object-fit: cover;">
              <div>
                <strong>${p.title}</strong>
                <br><span style="font-size: 0.75rem; color: var(--text-muted);">${p.variety || 'Natural'}</span>
              </div>
            </div>
          </td>
          <td><span class="badge badge-category">${p.category}</span></td>
          <td><strong>₹${parseFloat(p.price_per_unit).toFixed(2)}</strong> / ${p.unit}</td>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <input type="number" value="${p.stock_quantity}" id="stock-input-${p.id}" style="width: 70px; padding: 4px 6px; border: 1px solid var(--border-subtle); border-radius: 4px;">
              <button class="btn-action-sm" onclick="saveProduceStock('${p.id}')">Update</button>
            </div>
          </td>
          <td>${p.is_organic ? '🌿 Yes' : 'Standard'}</td>
          <td><span class="status-pill ${inStock ? 'status-active' : 'status-cancelled'}">${inStock ? 'In Stock' : 'Out of Stock'}</span></td>
          <td>
            <button class="btn-action-sm" style="color: #dc2626;" onclick="deleteProduce('${p.id}')">Delete</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load produce: ${err.message}</td></tr>`;
  }
}

async function saveProduceStock(productId) {
  const input = document.getElementById(`stock-input-${productId}`);
  if (!input) return;
  const newStock = parseFloat(input.value) || 0;

  try {
    await API.products.update(productId, { stock_quantity: newStock });
    showToast("Stock quantity updated!", "info");
    loadFarmerProduceList();
  } catch (err) {
    showToast(`Failed to update stock: ${err.message}`, "error");
  }
}

async function deleteProduce(productId) {
  if (!confirm("Are you sure you want to remove this produce listing?")) return;
  try {
    await API.products.delete(productId);
    showToast("Produce listing removed.", "info");
    loadFarmerProduceList();
    loadFarmerMetrics();
  } catch (err) {
    showToast(`Failed to delete produce: ${err.message}`, "error");
  }
}

async function loadFarmerOrdersList() {
  const container = document.getElementById("farmerOrdersTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading incoming orders...</td></tr>`;

  try {
    const res = await API.orders.list({ role: "farmer" });
    if (!res.orders || res.orders.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">No orders received yet for your produce.</td></tr>`;
      return;
    }

    container.innerHTML = res.orders.map(o => {
      const itemsList = (o.farmer_items || o.items || []).map(i => `${i.product_title || 'Item'} (${i.quantity} ${i.unit || 'kg'} = ₹${i.subtotal})`).join("<br>");
      return `
        <tr>
          <td><strong>${o.order_number}</strong></td>
          <td>${formatDateTime(o.created_at)}</td>
          <td>
            <strong>${o.customer_name || 'Customer'}</strong>
            <br><span style="font-size: 0.75rem; color: var(--text-muted);">📞 ${o.contact_phone}</span>
          </td>
          <td><div style="font-size: 0.82rem;">${itemsList}</div></td>
          <td>
            <strong>₹${parseFloat(o.farmer_total_earnings || o.total_farmer_payout || 0).toFixed(2)}</strong>
            <br><span style="font-size: 0.72rem; color: var(--primary);">Net Payout</span>
          </td>
          <td>
            <select class="form-control" style="padding: 4px 8px; font-size: 0.82rem;" onchange="updateFarmerOrderStatus('${o.id}', this.value)">
              <option value="pending" ${o.status === 'pending' ? 'selected' : ''}>Pending</option>
              <option value="confirmed" ${o.status === 'confirmed' ? 'selected' : ''}>Confirmed</option>
              <option value="shipped" ${o.status === 'shipped' ? 'selected' : ''}>Shipped</option>
              <option value="delivered" ${o.status === 'delivered' ? 'selected' : ''}>Delivered</option>
              <option value="cancelled" ${o.status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
            </select>
          </td>
          <td><span class="status-pill status-${o.status}">${o.status}</span></td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load orders: ${err.message}</td></tr>`;
  }
}

async function updateFarmerOrderStatus(orderId, newStatus) {
  try {
    await API.orders.updateStatus(orderId, newStatus);
    showToast(`Order status updated to '${newStatus}'!`, "info");
    loadFarmerOrdersList();
  } catch (err) {
    showToast(`Failed to update status: ${err.message}`, "error");
  }
}

async function loadFarmerEarnings() {
  const container = document.getElementById("farmerEarningsTableBody");
  if (!container) return;

  try {
    const res = await API.orders.list({ role: "farmer" });
    const orders = res.orders || [];
    
    if (orders.length === 0) {
      container.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">No earnings records yet.</td></tr>`;
      return;
    }

    container.innerHTML = orders.map(o => {
      const gross = (o.farmer_items || []).reduce((sum, i) => sum + (i.subtotal || 0), 0);
      const comm = (o.farmer_items || []).reduce((sum, i) => sum + (i.commission_amount || 0), 0);
      const net = (o.farmer_items || []).reduce((sum, i) => sum + (i.farmer_earnings || 0), 0);
      return `
        <tr>
          <td><strong>${o.order_number}</strong></td>
          <td>${formatDateTime(o.created_at)}</td>
          <td>₹${gross.toFixed(2)}</td>
          <td style="color: #d97706;">₹${comm.toFixed(2)} (5%)</td>
          <td style="font-weight: 700; color: var(--primary);">₹${net.toFixed(2)}</td>
          <td><span class="status-pill status-${o.status}">${o.status}</span></td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="6" style="color: #dc2626; padding: 20px;">Error: ${err.message}</td></tr>`;
  }
}

async function submitAddProduce(e) {
  e.preventDefault();
  const title = document.getElementById("addProduceTitle").value.trim();
  const category = document.getElementById("addProduceCategory").value;
  const variety = document.getElementById("addProduceVariety").value.trim();
  const unit = document.getElementById("addProduceUnit").value;
  const price = parseFloat(document.getElementById("addProducePrice").value) || 0;
  const stock = parseFloat(document.getElementById("addProduceStock").value) || 0;
  const isOrganic = document.getElementById("addProduceOrganic").checked;
  const imageUrl = document.getElementById("addProduceImageUrl").value.trim();
  const desc = document.getElementById("addProduceDesc").value.trim();

  if (!title || price <= 0) {
    showToast("Please provide valid produce title and price.", "error");
    return;
  }

  try {
    const res = await API.products.create({
      title: title,
      category: category,
      variety: variety,
      unit: unit,
      price_per_unit: price,
      stock_quantity: stock,
      is_organic: isOrganic,
      image_url: imageUrl,
      description: desc
    });

    closeModal("addProduceModal");
    showToast(res.message, "info");
    document.getElementById("addProduceForm").reset();
    loadFarmerProduceList();
    loadFarmerMetrics();
  } catch (err) {
    showToast(`Failed to add produce: ${err.message}`, "error");
  }
}

// ================= MACHINERY SELLER PANEL LOGIC =================
async function loadSellerData() {
  await loadSellerMetrics();
  if (AppState.activeSellerSubTab === "fleet") {
    await loadSellerFleetList();
  } else if (AppState.activeSellerSubTab === "bookings") {
    await loadSellerBookingsList();
  } else if (AppState.activeSellerSubTab === "earnings") {
    await loadSellerEarnings();
  }
}

async function loadSellerMetrics() {
  try {
    const fleetRes = await API.machinery.list({ seller_id: AppState.currentUser ? AppState.currentUser.id : "" });
    const bookRes = await API.bookings.list({ role: "machinery_seller" });

    const totalFleet = fleetRes.machinery ? fleetRes.machinery.length : 0;
    const bookings = bookRes.bookings || [];

    let grossTurnover = 0;
    let netEarnings = 0;
    let activeRentals = 0;
    let pendingRequests = 0;

    bookings.forEach(b => {
      grossTurnover += parseFloat(b.total_amount || 0);
      netEarnings += parseFloat(b.seller_payout || 0);
      if (b.status === "in_progress" || b.status === "approved") activeRentals++;
      if (b.status === "pending") pendingRequests++;
    });

    const commDeducted = grossTurnover - netEarnings;

    document.getElementById("sellerStatFleet").textContent = totalFleet;
    document.getElementById("sellerStatActive").textContent = activeRentals;
    document.getElementById("sellerStatPending").textContent = pendingRequests;
    document.getElementById("sellerStatGross").textContent = `₹${grossTurnover.toFixed(2)}`;
    document.getElementById("sellerStatNet").textContent = `₹${netEarnings.toFixed(2)}`;
    document.getElementById("sellerStatCommission").textContent = `₹${commDeducted.toFixed(2)} (Platform 10%)`;
  } catch (err) {
    console.error("Failed to load seller metrics:", err);
  }
}

async function loadSellerFleetList() {
  const container = document.getElementById("sellerFleetTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading machinery fleet...</td></tr>`;

  try {
    const res = await API.machinery.list({ seller_id: AppState.currentUser ? AppState.currentUser.id : "" });
    if (!res.machinery || res.machinery.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">No machinery listed in your fleet yet. Click "+ Add Machinery" to list tractors, harvesters, or pumps!</td></tr>`;
      return;
    }

    container.innerHTML = res.machinery.map(m => {
      const isAvailable = m.is_available == 1 || m.is_available === true;
      return `
        <tr>
          <td>
            <div style="display: flex; align-items: center; gap: 10px;">
              <img src="${m.image_url || 'https://images.unsplash.com/photo-1592878904946-b3cd8ae243d0?w=100'}" style="width: 50px; height: 44px; border-radius: 6px; object-fit: cover;">
              <div>
                <strong>${m.title}</strong>
                <br><span style="font-size: 0.75rem; color: var(--text-muted);">${m.model_info || ''}</span>
              </div>
            </div>
          </td>
          <td><span class="badge badge-category">${formatMachineryCategory(m.category)}</span></td>
          <td>₹${parseFloat(m.hourly_rate).toFixed(0)} /hr</td>
          <td>₹${parseFloat(m.daily_rate).toFixed(0)} /day</td>
          <td>${m.includes_operator ? `👨‍🔧 Yes (+₹${m.operator_charge_per_hour}/hr)` : 'Self-Drive'}</td>
          <td>
            <button class="btn-action-sm ${isAvailable ? 'btn-action-primary' : ''}" onclick="toggleMachineryAvailability('${m.id}', ${isAvailable ? 0 : 1})">
              ${isAvailable ? '● Available' : '○ Maintenance'}
            </button>
          </td>
          <td>
            <button class="btn-action-sm" style="color: #dc2626;" onclick="deleteMachinery('${m.id}')">Delete</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load fleet: ${err.message}</td></tr>`;
  }
}

async function toggleMachineryAvailability(machineryId, newStatusInt) {
  try {
    await API.machinery.update(machineryId, { is_available: newStatusInt });
    showToast(`Machinery availability status updated!`, "info");
    loadSellerFleetList();
    loadSellerMetrics();
  } catch (err) {
    showToast(`Failed to update status: ${err.message}`, "error");
  }
}

async function deleteMachinery(machineryId) {
  if (!confirm("Remove this machinery from your rental fleet?")) return;
  try {
    await API.machinery.delete(machineryId);
    showToast("Machinery removed.", "info");
    loadSellerFleetList();
    loadSellerMetrics();
  } catch (err) {
    showToast(`Failed to delete machinery: ${err.message}`, "error");
  }
}

async function loadSellerBookingsList() {
  const container = document.getElementById("sellerBookingsTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading rental requests...</td></tr>`;

  try {
    const res = await API.bookings.list({ role: "machinery_seller" });
    if (!res.bookings || res.bookings.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">No rental booking inquiries at the moment.</td></tr>`;
      return;
    }

    container.innerHTML = res.bookings.map(b => {
      return `
        <tr>
          <td><strong>${b.booking_number}</strong></td>
          <td>
            <strong>${b.customer_name || 'Customer'}</strong>
            <br><span style="font-size: 0.75rem; color: var(--text-muted);">📞 ${b.customer_phone || ''}</span>
          </td>
          <td>
            <strong>${b.machinery_title || 'Machine'}</strong>
            <br><span style="font-size: 0.75rem; color: var(--text-muted);">${b.duration_units} ${b.rental_type} ${b.with_operator ? '+ Operator' : ''}</span>
          </td>
          <td>
            ${formatDateTime(b.start_datetime)}
            <br><span style="font-size: 0.75rem; color: var(--text-muted);">📍 ${b.delivery_location}</span>
          </td>
          <td>
            <strong>₹${parseFloat(b.seller_payout || 0).toFixed(2)}</strong>
            <br><span style="font-size: 0.72rem; color: var(--primary);">Net (Gross: ₹${b.total_amount})</span>
          </td>
          <td><span class="status-pill status-${b.status}">${b.status}</span></td>
          <td>
            <div style="display: flex; gap: 4px; flex-wrap: wrap;">
              ${b.status === 'pending' ? `
                <button class="btn-action-sm btn-action-primary" onclick="updateSellerBookingStatus('${b.id}', 'approved')">Approve</button>
                <button class="btn-action-sm" style="color: #dc2626;" onclick="updateSellerBookingStatus('${b.id}', 'rejected')">Reject</button>
              ` : ''}
              ${b.status === 'approved' ? `
                <button class="btn-action-sm btn-action-primary" onclick="updateSellerBookingStatus('${b.id}', 'in_progress')">Dispatch</button>
              ` : ''}
              ${b.status === 'in_progress' ? `
                <button class="btn-action-sm btn-action-primary" onclick="updateSellerBookingStatus('${b.id}', 'completed')">Complete</button>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load bookings: ${err.message}</td></tr>`;
  }
}

async function updateSellerBookingStatus(bookingId, newStatus) {
  try {
    await API.bookings.updateStatus(bookingId, newStatus);
    showToast(`Rental booking marked as '${newStatus}'!`, "info");
    loadSellerBookingsList();
    loadSellerMetrics();
  } catch (err) {
    showToast(`Failed to update booking: ${err.message}`, "error");
  }
}

async function loadSellerEarnings() {
  const container = document.getElementById("sellerEarningsTableBody");
  if (!container) return;

  try {
    const res = await API.bookings.list({ role: "machinery_seller" });
    const bookings = res.bookings || [];

    if (bookings.length === 0) {
      container.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">No rental earnings records yet.</td></tr>`;
      return;
    }

    container.innerHTML = bookings.map(b => {
      const gross = parseFloat(b.total_amount || 0);
      const comm = parseFloat(b.commission_amount || 0);
      const net = parseFloat(b.seller_payout || 0);
      return `
        <tr>
          <td><strong>${b.booking_number}</strong></td>
          <td>${b.machinery_title}</td>
          <td>₹${gross.toFixed(2)}</td>
          <td style="color: #d97706;">₹${comm.toFixed(2)} (10%)</td>
          <td style="font-weight: 700; color: var(--primary);">₹${net.toFixed(2)}</td>
          <td><span class="status-pill status-${b.status}">${b.status}</span></td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="6" style="color: #dc2626; padding: 20px;">Error: ${err.message}</td></tr>`;
  }
}

async function submitAddMachinery(e) {
  e.preventDefault();
  const title = document.getElementById("addMachineryTitle").value.trim();
  const category = document.getElementById("addMachineryCategory").value;
  const model = document.getElementById("addMachineryModel").value.trim();
  const specs = document.getElementById("addMachinerySpecs").value.trim();
  const hourlyRate = parseFloat(document.getElementById("addMachineryHourlyRate").value) || 0;
  const dailyRate = parseFloat(document.getElementById("addMachineryDailyRate").value) || 0;
  const includesOp = document.getElementById("addMachineryIncludesOperator").checked;
  const opCharge = parseFloat(document.getElementById("addMachineryOperatorCharge").value) || 0;
  const location = document.getElementById("addMachineryLocation").value.trim();
  const imageUrl = document.getElementById("addMachineryImageUrl").value.trim();

  if (!title || hourlyRate <= 0 || dailyRate <= 0) {
    showToast("Please provide machinery title and valid rental rates.", "error");
    return;
  }

  try {
    const res = await API.machinery.create({
      title: title,
      category: category,
      model_info: model,
      specifications: specs,
      hourly_rate: hourlyRate,
      daily_rate: dailyRate,
      includes_operator: includesOp,
      operator_charge_per_hour: opCharge,
      location: location,
      image_url: imageUrl
    });

    closeModal("addMachineryModal");
    showToast(res.message, "info");
    document.getElementById("addMachineryForm").reset();
    loadSellerFleetList();
    loadSellerMetrics();
  } catch (err) {
    showToast(`Failed to add machinery: ${err.message}`, "error");
  }
}

// ================= SUPER ADMIN PANEL LOGIC =================
async function loadAdminData() {
  await loadAdminMetrics();
  if (AppState.activeAdminSubTab === "overview") {
    await loadAdminTransactions();
  } else if (AppState.activeAdminSubTab === "commission") {
    await loadAdminCommissionSettings();
  } else if (AppState.activeAdminSubTab === "users") {
    await loadAdminUsersList();
  } else if (AppState.activeAdminSubTab === "ledger") {
    await loadAdminTransactions();
  }
}

async function loadAdminMetrics() {
  try {
    const res = await API.admin.getMetrics();
    const m = res.metrics;

    document.getElementById("adminStatTurnover").textContent = `₹${m.total_platform_turnover.toLocaleString('en-IN')}`;
    document.getElementById("adminStatCommission").textContent = `₹${m.total_admin_commission.toLocaleString('en-IN')}`;
    document.getElementById("adminStatProduceComm").textContent = `₹${m.produce_commission_earned.toLocaleString('en-IN')}`;
    document.getElementById("adminStatMachineryComm").textContent = `₹${m.machinery_commission_earned.toLocaleString('en-IN')}`;
    document.getElementById("adminStatFarmers").textContent = m.total_farmers;
    document.getElementById("adminStatSellers").textContent = m.total_sellers;
    document.getElementById("adminStatCustomers").textContent = m.total_customers;
    document.getElementById("adminStatOrders").textContent = `${m.total_orders} Orders / ${m.total_bookings} Rentals`;
  } catch (err) {
    console.error("Failed to load admin metrics:", err);
  }
}

async function loadAdminCommissionSettings() {
  try {
    const res = await API.admin.getCommissionSettings();
    const s = res.settings;
    document.getElementById("adminSettingProduceCommission").value = s.produce_commission_percent;
    document.getElementById("adminSettingMachineryCommission").value = s.machinery_commission_percent;
  } catch (err) {
    console.error("Failed to load commission settings:", err);
  }
}

async function saveAdminCommissionSettings(e) {
  e.preventDefault();
  const prodPct = parseFloat(document.getElementById("adminSettingProduceCommission").value);
  const machPct = parseFloat(document.getElementById("adminSettingMachineryCommission").value);

  if (isNaN(prodPct) || isNaN(machPct)) {
    showToast("Please enter valid commission percentages.", "error");
    return;
  }

  try {
    const res = await API.admin.updateCommissionSettings(prodPct, machPct);
    showToast(res.message, "info");
    loadAdminMetrics();
  } catch (err) {
    showToast(`Failed to update commission settings: ${err.message}`, "error");
  }
}

async function loadAdminUsersList() {
  const container = document.getElementById("adminUsersTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading user accounts...</td></tr>`;

  try {
    const roleFilter = document.getElementById("adminUserRoleFilter") ? document.getElementById("adminUserRoleFilter").value : "";
    const res = await API.admin.getUsers(roleFilter);
    const users = res.users || [];

    if (users.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">No users found.</td></tr>`;
      return;
    }

    container.innerHTML = users.map(u => {
      const isActive = u.status === "active";
      return `
        <tr>
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <img src="${u.avatar_url || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + u.email}" style="width: 32px; height: 32px; border-radius: 50%;">
              <strong>${u.full_name}</strong>
            </div>
          </td>
          <td>${u.email}</td>
          <td><span class="badge badge-category">${formatRole(u.role)}</span></td>
          <td>${u.phone || 'N/A'}</td>
          <td>${u.location || 'India'}</td>
          <td><span class="status-pill status-${u.status}">${u.status}</span></td>
          <td>
            <button class="btn-action-sm ${isActive ? '' : 'btn-action-primary'}" onclick="toggleUserStatus('${u.id}', '${isActive ? 'suspended' : 'active'}')">
              ${isActive ? 'Suspend' : 'Activate'}
            </button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load users: ${err.message}</td></tr>`;
  }
}

async function toggleUserStatus(userId, newStatus) {
  try {
    await API.admin.toggleUserStatus(userId, newStatus);
    showToast(`User status set to '${newStatus}'.`, "info");
    loadAdminUsersList();
  } catch (err) {
    showToast(`Failed to update user: ${err.message}`, "error");
  }
}

async function loadAdminTransactions() {
  const container = document.getElementById("adminTransactionsTableBody");
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px;">Loading platform ledger...</td></tr>`;

  try {
    const res = await API.admin.getTransactions();
    const txns = res.transactions || [];

    if (txns.length === 0) {
      container.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">No financial transactions recorded yet.</td></tr>`;
      return;
    }

    container.innerHTML = txns.map(t => {
      const isRental = t.type === "machinery_rental";
      return `
        <tr>
          <td><strong>${t.ref_number}</strong></td>
          <td>${formatDateTime(t.created_at)}</td>
          <td>
            <span class="badge ${isRental ? 'badge-organic' : 'badge-category'}">
              ${isRental ? '🚜 Machinery Rental' : '🌾 Produce Order'}
            </span>
          </td>
          <td>${t.customer_name}</td>
          <td><strong>₹${t.gross_amount.toFixed(2)}</strong></td>
          <td style="color: #15803d; font-weight: 700;">₹${t.platform_commission.toFixed(2)}</td>
          <td style="color: var(--text-muted);">₹${t.vendor_net_payout.toFixed(2)}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color: #dc2626; padding: 20px;">Failed to load ledger: ${err.message}</td></tr>`;
  }
}

// ================= TAB SWITCHING HELPERS =================
function setCustomerSubTab(tab) {
  AppState.activeCustomerSubTab = tab;
  document.querySelectorAll("#customerTabs .tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".customer-subview").forEach(v => {
    v.style.display = v.id === `customer-view-${tab}` ? "block" : "none";
  });
  loadCustomerData();
}

function setFarmerSubTab(tab) {
  AppState.activeFarmerSubTab = tab;
  document.querySelectorAll("#farmerTabs .tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".farmer-subview").forEach(v => {
    v.style.display = v.id === `farmer-view-${tab}` ? "block" : "none";
  });
  loadFarmerData();
}

function setSellerSubTab(tab) {
  AppState.activeSellerSubTab = tab;
  document.querySelectorAll("#sellerTabs .tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".seller-subview").forEach(v => {
    v.style.display = v.id === `seller-view-${tab}` ? "block" : "none";
  });
  loadSellerData();
}

function setAdminSubTab(tab) {
  AppState.activeAdminSubTab = tab;
  document.querySelectorAll("#adminTabs .tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".admin-subview").forEach(v => {
    v.style.display = v.id === `admin-view-${tab}` ? "block" : "none";
  });
  loadAdminData();
}

// ================= EVENT LISTENERS & UI HELPERS =================
function setupEventListeners() {
  // Produce Filter Pills
  document.querySelectorAll("#produceFilterPills .filter-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#produceFilterPills .filter-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      AppState.produceFilter = pill.dataset.filter;
      loadProduceCatalog();
    });
  });

  // Machinery Filter Pills
  document.querySelectorAll("#machineryFilterPills .filter-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#machineryFilterPills .filter-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      AppState.machineryFilter = pill.dataset.filter;
      loadMachineryCatalog();
    });
  });

  // Search Listeners (Debounced)
  const prodSearch = document.getElementById("produceSearch");
  if (prodSearch) {
    prodSearch.addEventListener("input", debounce(() => loadProduceCatalog(), 300));
  }
  const machSearch = document.getElementById("machinerySearch");
  if (machSearch) {
    machSearch.addEventListener("input", debounce(() => loadMachineryCatalog(), 300));
  }

  // Booking Calculator inputs
  const rentType = document.getElementById("bookingRentalType");
  const duration = document.getElementById("bookingDuration");
  const opCheck = document.getElementById("bookingOperatorCheck");
  if (rentType) rentType.addEventListener("change", calculateBookingTotal);
  if (duration) duration.addEventListener("input", calculateBookingTotal);
  if (opCheck) opCheck.addEventListener("change", calculateBookingTotal);
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add("open");
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove("open");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'error' ? '⚠️' : '✅'}</span>
    <span style="flex: 1;">${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function formatDateTime(isoString) {
  if (!isoString) return "N/A";
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return isoString;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}
