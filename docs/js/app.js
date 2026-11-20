const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let state = {
  user: null,
  page: "dashboard",
  theme: "light",
  month: new Date().toISOString().slice(0, 7),
  charts: [],
  editing: null,
  authMode: "login",
};
const currency = () => state.user?.currency || "PHP";
const money = (n) =>
  new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: currency(),
    maximumFractionDigits: 2,
  }).format(Number(n || 0));
async function api(path, opts = {}) {
  const res = await fetch("/api" + path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  let j = await res
    .json()
    .catch(() => ({ success: false, error: "Unexpected server response." }));
  if (!res.ok || !j.success) {
    if (res.status === 401) {
      showAuth();
    }
    throw new Error(j.error || "Request failed");
  }
  return j.data;
}
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2600);
}
function esc(s = "") {
  return String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
function showAuth() {
  state.user = null;
  $("#appView").classList.add("hidden");
  $("#authView").classList.remove("hidden");
}
function setAuthMode(mode) {
  state.authMode = mode;
  $("#authTitle").textContent =
    mode === "login" ? "Welcome back" : "Create your account";
  $("#authSubtitle").textContent =
    mode === "login"
      ? "Sign in to manage your personal finances."
      : "Start organizing your money in one secure place.";
  $("#nameField").classList.toggle("hidden", mode === "login");
  $("#authSubmit").textContent =
    mode === "login" ? "Sign in" : "Create account";
  $("#authSwitch").innerHTML =
    mode === "login"
      ? 'New to BlueWallet? <button type="button" class="text-btn" id="toggleAuth">Create an account</button>'
      : 'Already have an account? <button type="button" class="text-btn" id="toggleAuth">Sign in</button>';
  $("#toggleAuth").onclick = () =>
    setAuthMode(mode === "login" ? "register" : "login");
}
$("#authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = Object.fromEntries(f.entries());
  try {
    await api("/auth/" + state.authMode, {
      method: "POST",
      body: JSON.stringify(body),
    });
    await boot();
  } catch (err) {
    toast(err.message);
  }
});
async function boot() {
  try {
    const me = await api("/auth/me");
    if (!me.authenticated) {
      showAuth();
      return;
    }
    state.user = me.user;
    state.theme = me.user.theme || "light";
    applyTheme(state.theme);
    $("#authView").classList.add("hidden");
    $("#appView").classList.remove("hidden");
    $("#sideName").textContent = me.user.full_name || "My account";
    $("#sideEmail").textContent = me.user.email;
    $("#avatar").textContent = (me.user.full_name || "B")[0].toUpperCase();
    $("#todayLabel").textContent = new Date().toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    render();
  } catch (e) {
    showAuth();
  }
}
function applyTheme(t) {
  state.theme =
    t === "system"
      ? matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : t;
  document.body.classList.toggle("dark", state.theme === "dark");
  $("#themeToggle").textContent = state.theme === "dark" ? "☀" : "☾";
}
$("#toggleAuth").onclick = () => setAuthMode("register");
$("#themeToggle").onclick = async () => {
  const t = state.theme === "dark" ? "light" : "dark";
  applyTheme(t);
  try {
    await api("/settings", {
      method: "PUT",
      body: JSON.stringify({ theme: t }),
    });
  } catch {}
};
$("#logoutBtn").onclick = async () => {
  try {
    await api("/auth/logout", { method: "POST", body: "{}" });
  } catch {}
  showAuth();
};
$("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");
$("#quickAdd").onclick = () => openTransaction();
$("#closeModal").onclick = closeModal;
$("#modalLayer").addEventListener("click", (e) => {
  if (e.target.id === "modalLayer") closeModal();
});
$("#mainNav").addEventListener("click", (e) => {
  const b = e.target.closest("[data-page]");
  if (b) {
    state.page = b.dataset.page;
    $("#sidebar").classList.remove("open");
    render();
  }
});
function navActive() {
  $$(".nav-item[data-page]").forEach((b) =>
    b.classList.toggle("active", b.dataset.page === state.page),
  );
}
function pageHeader(title) {
  $("#pageTitle").textContent = title;
  navActive();
}
function destroyCharts() {
  state.charts.forEach((c) => c.destroy());
  state.charts = [];
}
function chart(el, type, data, options = {}) {
  if (!window.Chart || !el) return;
  const c = new Chart(el, {
    type,
    data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            usePointStyle: true,
            boxWidth: 8,
            color: getComputedStyle(document.body).getPropertyValue("--muted"),
          },
        },
      },
      scales:
        type === "pie"
          ? {}
          : {
              x: { grid: { display: false }, ticks: { color: "#91a1b2" } },
              y: {
                grid: { color: "rgba(140,160,180,.14)" },
                ticks: { color: "#91a1b2" },
              },
            },
      ...options,
    },
  });
  state.charts.push(c);
}
async function render() {
  destroyCharts();
  const names = {
    dashboard: "Overview",
    transactions: "Transactions",
    calendar: "Wallet calendar",
    budgets: "Budget management",
    categories: "Categories",
    reports: "Reports & statistics",
    notes: "Notes",
    vault: "Password vault",
    settings: "Settings",
  };
  pageHeader(names[state.page]);
  const target = $("#pageContent");
  target.innerHTML = '<div class="empty">Loading your finance data…</div>';
  try {
    switch (state.page) {
      case "dashboard":
        await dashboardPage(target);
        break;
      case "transactions":
        await transactionsPage(target);
        break;
      case "calendar":
        await calendarPage(target);
        break;
      case "budgets":
        await budgetsPage(target);
        break;
      case "categories":
        await categoriesPage(target);
        break;
      case "reports":
        await reportsPage(target);
        break;
      case "notes":
        await notesPage(target);
        break;
      case "vault":
        await vaultPage(target);
        break;
      case "settings":
        await settingsPage(target);
        break;
    }
  } catch (e) {
    target.innerHTML = `<div class="panel empty">${esc(e.message)}</div>`;
  }
}
function stat(label, value, icon, foot = "Updated just now") {
  return `<div class="stat-card"><div class="stat-top"><span>${label}</span><span class="stat-icon">${icon}</span></div><div class="stat-value">${value}</div><div class="stat-foot">${foot}</div></div>`;
}
function transactionRows(rows) {
  if (!rows.length)
    return '<tr><td colspan="6"><div class="empty"><strong>No transactions yet</strong>Add income or expenses to see them here.</div></td></tr>';
  return rows
    .map(
      (t) =>
        `<tr><td>${esc(t.transaction_date)}</td><td><span class="category-dot" style="background:${esc(t.color || "#268bd2")}"></span>${esc(t.category || t.destination || "Transfer")}</td><td>${esc(t.note || "—")}</td><td><span class="type-pill ${t.kind}">${t.kind}</span></td><td class="${t.kind === "income" ? "positive" : t.kind === "expense" ? "negative" : ""}">${t.kind === "expense" ? "-" : t.kind === "income" ? "+" : ""}${money(t.amount)}</td><td><div class="table-actions"><button data-edit-tx="${t.id}">Edit</button><button data-delete-tx="${t.id}">Delete</button></div></td></tr>`,
    )
    .join("");
}
async function dashboardPage(el) {
  const d = await api("/dashboard?month=" + state.month);
  el.innerHTML = `<div class="welcome-row"><div><h3>Hello, ${esc(state.user.full_name || "there")} 👋</h3><p>Here’s what’s happening with your money this month.</p></div><button class="btn primary" id="dashAdd">＋ New transaction</button></div><div class="stats-grid">${stat("Total balance", money(d.balance), "◈", "Across your wallets")}${stat("Income this month", money(d.income), "↗", "Money received")}${stat("Expenses this month", money(d.expense), "↘", "Money spent")}${stat("Monthly savings", money(d.savings), "✧", d.savings >= 0 ? "Income minus expenses" : "You spent more than you earned")}</div><div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h3>Income vs expenses</h3><p>Monthly financial activity</p></div><input type="month" class="select-small" id="dashMonth" value="${state.month}"></div><div class="chart-wrap"><canvas id="incomeChart"></canvas></div></section><section class="panel"><div class="panel-head"><div><h3>Spending by category</h3><p>Expense breakdown</p></div></div><div class="chart-wrap small"><canvas id="categoryChart"></canvas></div></section></div><section class="panel"><div class="panel-head"><div><h3>Recent transactions</h3><p>Your latest financial activity</p></div><button class="btn light" id="allTx">View all</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Type</th><th>Amount</th><th></th></tr></thead><tbody>${transactionRows(d.recent)}</tbody></table></div></section>`;
  $("#dashAdd").onclick = () => openTransaction();
  $("#allTx").onclick = () => {
    state.page = "transactions";
    render();
  };
  $("#dashMonth").onchange = (e) => {
    state.month = e.target.value;
    render();
  };
  chart(
    $("#incomeChart"),
    "bar",
    {
      labels: ["Income", "Expenses", "Savings"],
      datasets: [
        {
          label: "Amount",
          data: [d.income, d.expense, d.savings],
          backgroundColor: ["#20ae83", "#e76a7f", "#369bd4"],
          borderRadius: 8,
          maxBarThickness: 45,
        },
      ],
    },
    { plugins: { legend: { display: false } } },
  );
  chart($("#categoryChart"), "doughnut", {
    labels: d.categories.filter((x) => x.total > 0).map((x) => x.name),
    datasets: [
      {
        data: d.categories.filter((x) => x.total > 0).map((x) => x.total),
        backgroundColor: d.categories
          .filter((x) => x.total > 0)
          .map((x) => x.color),
        borderWidth: 0,
      },
    ],
  });
  wireTxActions();
}
async function transactionsPage(el) {
  const [rows, cats, accounts] = await Promise.all([
    api("/transactions"),
    api("/categories"),
    api("/accounts"),
  ]);
  el.innerHTML = `<div class="toolbar"><div class="toolbar-left"><input class="search" id="txSearch" placeholder="Search description or category…"><select class="select-small" id="txKind"><option value="">All types</option><option value="income">Income</option><option value="expense">Expense</option><option value="transfer">Transfer</option></select><input type="month" class="select-small" id="txMonth" value="${state.month}"></div><div class="toolbar-right"><button class="btn light" id="exportCsv">Export CSV</button><button class="btn primary" id="addTx">＋ Add transaction</button></div></div><section class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Type</th><th>Amount</th><th>Actions</th></tr></thead><tbody id="txBody">${transactionRows(rows)}</tbody></table></div></section>`;
  const filter = () => {
    const q = $("#txSearch").value.toLowerCase(),
      k = $("#txKind").value,
      m = $("#txMonth").value;
    const filtered = rows.filter(
      (t) =>
        (!q ||
          (t.note || "").toLowerCase().includes(q) ||
          (t.category || "").toLowerCase().includes(q)) &&
        (!k || t.kind === k) &&
        (!m || t.transaction_date.startsWith(m)),
    );
    $("#txBody").innerHTML = transactionRows(filtered);
    wireTxActions();
  };
  $("#txSearch").oninput = filter;
  $("#txKind").onchange = filter;
  $("#txMonth").onchange = filter;
  $("#addTx").onclick = () => openTransaction();
  $("#exportCsv").onclick = () =>
    downloadCsv(rows, "bluewallet-transactions.csv");
  wireTxActions();
}
function wireTxActions() {
  $$("[data-edit-tx]").forEach(
    (b) =>
      (b.onclick = async () => {
        const rows = await api("/transactions");
        const t = rows.find((x) => x.id == b.dataset.editTx);
        if (t) openTransaction(t);
      }),
  );
  $$("[data-delete-tx]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (!confirm("Delete this transaction?")) return;
        try {
          await api("/transactions/" + b.dataset.deleteTx, {
            method: "DELETE",
          });
          toast("Transaction deleted");
          render();
        } catch (e) {
          toast(e.message);
        }
      }),
  );
}
async function openTransaction(item = null) {
  const [cats, accounts] = await Promise.all([
    api("/categories"),
    api("/accounts"),
  ]);
  state.editing = item;
  const kind = item?.kind || "expense";
  openModal(
    item ? "EDIT ENTRY" : "NEW ENTRY",
    item ? "Edit transaction" : "Add transaction",
    `<form id="txForm"><div class="field"><label>Transaction type</label><select name="kind" id="txType"><option value="income" ${kind === "income" ? "selected" : ""}>Income</option><option value="expense" ${kind === "expense" ? "selected" : ""}>Expense</option><option value="transfer" ${kind === "transfer" ? "selected" : ""}>Transfer</option></select></div><div class="form-grid"><div class="field"><label>Amount</label><input name="amount" type="number" min="0.01" step="0.01" required value="${item?.amount || ""}" placeholder="0.00"></div><div class="field"><label>Date</label><input name="transaction_date" type="date" required value="${item?.transaction_date || new Date().toISOString().slice(0, 10)}"></div><div class="field"><label>Wallet / account</label><select name="account_id">${accounts.map((a) => `<option value="${a.id}" ${item?.account_id === a.id ? "selected" : ""}>${esc(a.name)}</option>`).join("")}</select></div><div class="field" id="categoryField"><label>Category</label><select name="category_id">${cats
      .filter((c) => c.kind === kind)
      .map(
        (c) =>
          `<option value="${c.id}" ${item?.category_id === c.id ? "selected" : ""}>${esc(c.name)}</option>`,
      )
      .join(
        "",
      )}</select></div><div class="field wide" id="destinationField"><label>Destination (for transfer record)</label><input name="destination" value="${esc(item?.destination || "")}" placeholder="Another wallet or account"></div><div class="field wide"><label>Note / description</label><input name="note" value="${esc(item?.note || "")}" placeholder="What was this for?"></div></div><div class="modal-actions"><button type="button" class="btn light" id="cancelTx">Cancel</button><button class="btn primary">${item ? "Save changes" : "Save transaction"}</button></div></form>`,
  );
  const type = $("#txType");
  const update = () => {
    const k = type.value;
    $("#categoryField").classList.toggle("hidden", k === "transfer");
    $("#destinationField").classList.toggle("hidden", k !== "transfer");
    const select = $("[name=category_id]");
    select.innerHTML = cats
      .filter((c) => c.kind === k)
      .map((c) => `<option value="${c.id}">${esc(c.name)}</option>`)
      .join("");
  };
  type.onchange = update;
  update();
  if (item) {
    $("[name=category_id]").value = item.category_id || "";
  }
  $("#cancelTx").onclick = closeModal;
  $("#txForm").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    data.amount = Number(data.amount);
    data.account_id = data.account_id ? Number(data.account_id) : null;
    data.category_id = data.category_id ? Number(data.category_id) : null;
    try {
      await api(item ? "/transactions/" + item.id : "/transactions", {
        method: item ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      closeModal();
      toast(item ? "Transaction updated" : "Transaction saved");
      render();
    } catch (err) {
      toast(err.message);
    }
  };
}
function openModal(eyebrow, title, html) {
  $("#modalEyebrow").textContent = eyebrow;
  $("#modalTitle").textContent = title;
  $("#modalBody").innerHTML = html;
  $("#modalLayer").classList.remove("hidden");
}
function closeModal() {
  $("#modalLayer").classList.add("hidden");
  state.editing = null;
}
async function calendarPage(el) {
  const rows = await api("/calendar?month=" + state.month);
  const [y, m] = state.month.split("-").map(Number);
  const first = new Date(y, m - 1, 1).getDay(),
    days = new Date(y, m, 0).getDate();
  const map = {};
  rows.forEach((r) => {
    map[r.transaction_date] ??= {};
    map[r.transaction_date][r.kind] = r.total;
  });
  const cells = Array(first).fill("<div></div>");
  for (let d = 1; d <= days; d++) {
    const key = `${state.month}-${String(d).padStart(2, "0")}`,
      v = map[key] || {};
    cells.push(
      `<div class="day ${key === new Date().toISOString().slice(0, 10) ? "today" : ""}" data-day="${key}">${d}${v.income ? `<small>+${money(v.income)}</small>` : ""}${v.expense ? `<small class="negative">-${money(v.expense)}</small>` : ""}</div>`,
    );
  }
  el.innerHTML = `<div class="toolbar"><div><h3 class="section-title">Monthly wallet activity</h3><p class="muted">Select a date to view its transactions.</p></div><div class="toolbar-right"><input type="month" class="select-small" id="calendarMonth" value="${state.month}"><button class="btn primary" id="calendarAdd">＋ Add transaction</button></div></div><div class="calendar-layout"><section class="panel"><div class="calendar-head"><strong>${new Date(y, m - 1).toLocaleDateString(undefined, { month: "long", year: "numeric" })}</strong><div><button class="icon-btn" id="prevMonth">‹</button> <button class="icon-btn" id="nextMonth">›</button></div></div><div class="calendar-grid">${["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((x) => `<div class="weekday">${x}</div>`).join("")}${cells.join("")}</div></section><section class="panel"><div class="panel-head"><div><h3 id="selectedDateTitle">Choose a date</h3><p>Daily transaction summary</p></div></div><div id="dayDetails" class="empty">Select a date on the calendar.</div></section></div>`;
  $("#calendarMonth").onchange = (e) => {
    state.month = e.target.value;
    render();
  };
  $("#prevMonth").onclick = () => changeMonth(-1);
  $("#nextMonth").onclick = () => changeMonth(1);
  $("#calendarAdd").onclick = () => openTransaction();
  $$("[data-day]").forEach(
    (b) =>
      (b.onclick = async () => {
        $$(".day").forEach((x) => x.classList.remove("selected"));
        b.classList.add("selected");
        const all = await api(
          "/transactions?from=" + b.dataset.day + "&to=" + b.dataset.day,
        );
        const inc = all
            .filter((t) => t.kind === "income")
            .reduce((s, t) => s + t.amount, 0),
          out = all
            .filter((t) => t.kind === "expense")
            .reduce((s, t) => s + t.amount, 0);
        $("#selectedDateTitle").textContent = new Date(
          b.dataset.day + "T12:00:00",
        ).toLocaleDateString(undefined, {
          weekday: "long",
          month: "long",
          day: "numeric",
        });
        $("#dayDetails").innerHTML =
          `<div class="stats-grid" style="grid-template-columns:1fr 1fr"><div><small class="muted">Income</small><h3 class="positive">${money(inc)}</h3></div><div><small class="muted">Expenses</small><h3 class="negative">${money(out)}</h3></div></div><div class="table-wrap"><table class="data-table"><tbody>${transactionRows(all)}</tbody></table></div>`;
        wireTxActions();
      }),
  );
}
function changeMonth(delta) {
  const [y, m] = state.month.split("-").map(Number),
    d = new Date(y, m - 1 + delta, 1);
  state.month = d.toISOString().slice(0, 7);
  render();
}
async function budgetsPage(el) {
  const [rows, cats] = await Promise.all([
    api("/budgets?month=" + state.month),
    api("/categories"),
  ]);
  el.innerHTML = `<div class="toolbar"><div><h3 class="section-title">Monthly spending limits</h3><p class="muted">Set a limit and keep an eye on category spending.</p></div><div class="toolbar-right"><input type="month" id="budgetMonth" class="select-small" value="${state.month}"><button class="btn primary" id="addBudget">＋ Set budget</button></div></div><div class="grid-cards">${
    rows.length
      ? rows
          .map((b) => {
            const pct = b.amount ? Math.round((b.spent / b.amount) * 100) : 0;
            return `<div class="budget-card"><div class="budget-title"><span><span class="category-dot" style="background:${b.color}"></span>${esc(b.category)}</span><span>${pct}%</span></div><div class="progress ${pct > 100 ? "over" : ""}"><span style="width:${Math.min(pct, 100)}%"></span></div><div class="budget-meta"><span>${money(b.spent)} spent</span><span>${money(b.amount)} limit</span></div><div class="budget-meta" style="margin-top:8px"><span>${money(b.amount - b.spent)} remaining</span><button class="text-btn" data-del-budget="${b.id}">Remove</button></div></div>`;
          })
          .join("")
      : '<div class="panel empty">No budgets for this month. Add a category limit to get started.</div>'
  }</div>`;
  $("#budgetMonth").onchange = (e) => {
    state.month = e.target.value;
    render();
  };
  $("#addBudget").onclick = () => {
    openModal(
      "BUDGET PLANNER",
      "Set a category budget",
      `<form id="budgetForm"><div class="field"><label>Expense category</label><select name="category_id" required>${cats
        .filter((c) => c.kind === "expense")
        .map((c) => `<option value="${c.id}">${esc(c.name)}</option>`)
        .join(
          "",
        )}</select></div><div class="field"><label>Monthly limit</label><input name="amount" type="number" min="0.01" step="0.01" required></div><div class="field"><label>Month</label><input name="month" type="month" value="${state.month}" required></div><div class="modal-actions"><button type="button" class="btn light" onclick="closeModal()">Cancel</button><button class="btn primary">Save budget</button></div></form>`,
    );
    $("#budgetForm").onsubmit = async (e) => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(e.target));
      d.category_id = Number(d.category_id);
      d.amount = Number(d.amount);
      try {
        await api("/budgets", { method: "POST", body: JSON.stringify(d) });
        closeModal();
        toast("Budget saved");
        render();
      } catch (x) {
        toast(x.message);
      }
    };
  };
  $$("[data-del-budget]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (confirm("Remove this budget?")) {
          await api("/budgets/" + b.dataset.delBudget, { method: "DELETE" });
          render();
        }
      }),
  );
}
async function categoriesPage(el) {
  const cats = await api("/categories");
  el.innerHTML = `<div class="toolbar"><div><h3 class="section-title">Your categories</h3><p class="muted">Organize income and expenses with your own labels.</p></div><button class="btn primary" id="addCategory">＋ Add category</button></div><div class="grid-cards">${cats.map((c) => `<div class="category-card"><div class="category-symbol" style="color:${c.color}">◆</div><div style="flex:1"><strong>${esc(c.name)}</strong><small>${c.kind} ${c.is_default ? "· default" : ""}</small></div>${c.is_default ? "" : `<button class="icon-btn" data-del-cat="${c.id}" title="Delete">✕</button>`}</div>`).join("")}</div>`;
  $("#addCategory").onclick = () => {
    openModal(
      "PERSONALIZE",
      "Create a category",
      `<form id="catForm"><div class="field"><label>Category name</label><input name="name" required maxlength="60"></div><div class="field"><label>Type</label><select name="kind"><option value="expense">Expense</option><option value="income">Income</option></select></div><div class="field"><label>Color</label><input class="color-input" name="color" type="color" value="#268bd2"></div><div class="modal-actions"><button type="button" class="btn light" onclick="closeModal()">Cancel</button><button class="btn primary">Create category</button></div></form>`,
    );
    $("#catForm").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("/categories", {
          method: "POST",
          body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
        });
        closeModal();
        render();
        toast("Category created");
      } catch (x) {
        toast(x.message);
      }
    };
  };
  $$("[data-del-cat]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (
          confirm(
            "Delete this category? Transactions will remain, but will no longer be linked to it.",
          )
        ) {
          try {
            await api("/categories/" + b.dataset.delCat, { method: "DELETE" });
            render();
          } catch (e) {
            toast(e.message);
          }
        }
      }),
  );
}
async function reportsPage(el) {
  const d = await api("/reports");
  const months = [...new Set(d.monthly.map((x) => x.month))];
  const inc = months.map((m) =>
      d.monthly
        .filter((x) => x.month === m && x.kind === "income")
        .reduce((s, x) => s + x.total, 0),
    ),
    exp = months.map((m) =>
      d.monthly
        .filter((x) => x.month === m && x.kind === "expense")
        .reduce((s, x) => s + x.total, 0),
    );
  el.innerHTML = `<div class="toolbar"><div><h3 class="section-title">Financial reports</h3><p class="muted">Understand trends and where your money goes.</p></div><div class="toolbar-right"><button class="btn light" id="reportCsv">Export CSV</button><button class="btn primary" id="reportPrint">Print / Save PDF</button></div></div><div class="dashboard-grid"><section class="panel"><div class="panel-head"><h3>Income & expense trend</h3></div><div class="chart-wrap"><canvas id="reportLine"></canvas></div></section><section class="panel"><div class="panel-head"><h3>Expense categories</h3></div><div class="chart-wrap"><canvas id="reportPie"></canvas></div></section></div><section class="panel"><div class="panel-head"><h3>Monthly breakdown</h3></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Month</th><th>Income</th><th>Expenses</th><th>Net savings</th></tr></thead><tbody>${
    months.length
      ? months
          .map((m) => {
            const i = inc[months.indexOf(m)],
              x = exp[months.indexOf(m)];
            return `<tr><td>${m}</td><td class="positive">${money(i)}</td><td class="negative">${money(x)}</td><td>${money(i - x)}</td></tr>`;
          })
          .join("")
      : '<tr><td colspan="4" class="empty">No report data yet.</td></tr>'
  }</tbody></table></div></section>`;
  chart($("#reportLine"), "line", {
    labels: months,
    datasets: [
      {
        label: "Income",
        data: inc,
        borderColor: "#18a879",
        backgroundColor: "#18a87922",
        tension: 0.35,
        fill: true,
      },
      {
        label: "Expenses",
        data: exp,
        borderColor: "#e65e76",
        backgroundColor: "#e65e7622",
        tension: 0.35,
        fill: true,
      },
    ],
  });
  chart($("#reportPie"), "pie", {
    labels: d.categories.map((x) => x.name),
    datasets: [
      {
        data: d.categories.map((x) => x.total),
        backgroundColor: d.categories.map((x) => x.color),
        borderWidth: 0,
      },
    ],
  });
  $("#reportCsv").onclick = () =>
    downloadCsv(d.monthly, "bluewallet-monthly-report.csv");
  $("#reportPrint").onclick = () => window.print();
}
async function notesPage(el) {
  const notes = await api("/notes");
  el.innerHTML = `<div class="toolbar"><div><h3 class="section-title">Your notes</h3><p class="muted">Keep reminders, ideas, and financial plans close.</p></div><div class="toolbar-right"><input id="noteSearch" class="search" placeholder="Search notes…"><button id="addNote" class="btn primary">＋ New note</button></div></div><div id="noteGrid" class="note-grid">${notes.length ? notes.map(noteCard).join("") : '<div class="panel empty">No notes yet. Create your first note.</div>'}</div>`;
  $("#noteSearch").oninput = (e) => {
    const q = e.target.value.toLowerCase();
    $("#noteGrid").innerHTML =
      notes
        .filter((n) =>
          (n.title + n.body + n.category).toLowerCase().includes(q),
        )
        .map(noteCard)
        .join("") || '<div class="panel empty">No matching notes.</div>';
    wireNotes();
  };
  $("#addNote").onclick = () => openNote();
  wireNotes();
}
function noteCard(n) {
  return `<article class="note-card" style="background:${esc(n.color)}"><div class="note-actions"><button data-pin-note="${n.id}" title="Pin">${n.pinned ? "📌" : "⌖"}</button><button data-edit-note="${n.id}" title="Edit">✎</button><button data-del-note="${n.id}" title="Delete">×</button></div><h4>${esc(n.title)}</h4><p>${esc(n.body)}</p><small>${esc(n.category)}</small></article>`;
}
function wireNotes() {
  $$("[data-pin-note]").forEach(
    (b) =>
      (b.onclick = async () => {
        const n = (await api("/notes")).find((x) => x.id == b.dataset.pinNote);
        await api("/notes/" + n.id, {
          method: "PUT",
          body: JSON.stringify({ ...n, pinned: !n.pinned }),
        });
        render();
      }),
  );
  $$("[data-edit-note]").forEach(
    (b) =>
      (b.onclick = async () => {
        const n = (await api("/notes")).find((x) => x.id == b.dataset.editNote);
        openNote(n);
      }),
  );
  $$("[data-del-note]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (confirm("Delete this note?")) {
          await api("/notes/" + b.dataset.delNote, { method: "DELETE" });
          render();
        }
      }),
  );
}
function openNote(n = null) {
  openModal(
    "NOTE MANAGEMENT",
    n ? "Edit note" : "Create a note",
    `<form id="noteForm"><div class="field"><label>Title</label><input name="title" required value="${esc(n?.title || "")}"></div><div class="field"><label>Note</label><textarea name="body" rows="5">${esc(n?.body || "")}</textarea></div><div class="form-grid"><div class="field"><label>Category</label><input name="category" value="${esc(n?.category || "General")}"></div><div class="field"><label>Card color</label><input name="color" class="color-input" type="color" value="${n?.color || "#fff2a8"}"></div></div><label><input type="checkbox" name="pinned" ${n?.pinned ? "checked" : ""}> Pin this note</label><div class="modal-actions"><button type="button" class="btn light" onclick="closeModal()">Cancel</button><button class="btn primary">Save note</button></div></form>`,
  );
  $("#noteForm").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target),
      d = Object.fromEntries(f);
    d.pinned = f.has("pinned");
    try {
      await api(n ? "/notes/" + n.id : "/notes", {
        method: n ? "PUT" : "POST",
        body: JSON.stringify(d),
      });
      closeModal();
      render();
      toast("Note saved");
    } catch (x) {
      toast(x.message);
    }
  };
}
async function vaultPage(el) {
  const entries = await api("/vault");
  el.innerHTML = `<div class="toolbar"><div><h3 class="section-title">Password vault</h3><p class="muted">Store website credentials encrypted in your local app database.</p></div><button class="btn primary" id="addVault">＋ Add credential</button></div><section class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>Website</th><th>Username</th><th>URL</th><th>Created</th><th>Actions</th></tr></thead><tbody>${entries.length ? entries.map((v) => `<tr><td><strong>${esc(v.site)}</strong></td><td>${esc(v.username)}</td><td>${v.url ? `<a href="${esc(v.url)}" target="_blank" rel="noopener">Open site ↗</a>` : "—"}</td><td>${esc((v.created_at || "").slice(0, 10))}</td><td><div class="table-actions"><button data-reveal="${v.id}">Reveal</button><button data-vault-del="${v.id}">Delete</button></div></td></tr>`).join("") : '<tr><td colspan="5"><div class="empty"><strong>No saved credentials</strong>Add a website login to your vault.</div></td></tr>'}</tbody></table></div></section><p class="muted tiny" style="margin-top:14px">Security note: vault passwords are encrypted at rest with a Fernet key. Keep your VAULT_KEY secret and back it up securely; losing it makes saved passwords unrecoverable.</p>`;
  $("#addVault").onclick = () => {
    openModal(
      "SECURE VAULT",
      "Add login details",
      `<form id="vaultForm"><div class="field"><label>Website / service</label><input name="site" required></div><div class="field"><label>Website URL</label><input name="url" type="url" placeholder="https://example.com"></div><div class="field"><label>Username / email</label><input name="username"></div><div class="field"><label>Password</label><input name="password" type="password" required autocomplete="new-password"></div><div class="field"><label>Notes</label><textarea name="notes" rows="2"></textarea></div><div class="modal-actions"><button type="button" class="btn light" onclick="closeModal()">Cancel</button><button class="btn primary">Save securely</button></div></form>`,
    );
    $("#vaultForm").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("/vault", {
          method: "POST",
          body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
        });
        closeModal();
        render();
        toast("Credential saved");
      } catch (x) {
        toast(x.message);
      }
    };
  };
  $$("[data-reveal]").forEach(
    (b) =>
      (b.onclick = async () => {
        try {
          const d = await api("/vault/" + b.dataset.reveal + "/reveal", {
            method: "POST",
            body: "{}",
          });
          openModal(
            "VAULT PASSWORD",
            "Credential revealed",
            `<p class="muted">Copy this password only when needed. Avoid sharing it.</p><div class="field"><input id="revealedPassword" type="text" readonly value="${esc(d.password)}"></div><div class="modal-actions"><button class="btn light" id="copyPass">Copy password</button><button class="btn primary" onclick="closeModal()">Close</button></div>`,
          );
          $("#copyPass").onclick = () => {
            navigator.clipboard?.writeText(d.password);
            toast("Password copied");
          };
        } catch (e) {
          toast(e.message);
        }
      }),
  );
  $$("[data-vault-del]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (confirm("Permanently delete this credential?")) {
          await api("/vault/" + b.dataset.vaultDel, { method: "DELETE" });
          render();
        }
      }),
  );
}
async function settingsPage(el) {
  const [profile, s] = await Promise.all([api("/profile"), api("/settings")]);
  el.innerHTML = `<div class="settings-grid"><section class="panel"><div class="panel-head"><div><h3>Profile information</h3><p>Manage your account details.</p></div></div><form id="profileForm"><div class="field"><label>Full name</label><input name="full_name" required value="${esc(profile.full_name)}"></div><div class="field"><label>Email address</label><input value="${esc(profile.email)}" disabled></div><div class="field"><label>Default currency</label><select name="currency">${[
    ["PHP", "Philippine peso (PHP)"],
    ["USD", "US dollar (USD)"],
    ["EUR", "Euro (EUR)"],
    ["GBP", "British pound (GBP)"],
    ["JPY", "Japanese yen (JPY)"],
    ["SGD", "Singapore dollar (SGD)"],
  ]
    .map(
      ([v, l]) =>
        `<option value="${v}" ${profile.currency === v ? "selected" : ""}>${l}</option>`,
    )
    .join(
      "",
    )}</select></div><button class="btn primary">Save profile</button></form></section><section class="panel"><div class="panel-head"><div><h3>Appearance & preferences</h3><p>Personalize your workspace.</p></div></div><form id="settingsForm"><div class="setting-row"><div><strong>Theme</strong><small>Choose light, dark, or system appearance.</small></div><select name="theme"><option value="light" ${s.theme === "light" ? "selected" : ""}>Light</option><option value="dark" ${s.theme === "dark" ? "selected" : ""}>Dark</option><option value="system" ${s.theme === "system" ? "selected" : ""}>System</option></select></div><div class="setting-row"><div><strong>Date format</strong><small>Display preference for dates.</small></div><select name="date_format"><option ${s.date_format === "YYYY-MM-DD" ? "selected" : ""}>YYYY-MM-DD</option><option ${s.date_format === "DD/MM/YYYY" ? "selected" : ""}>DD/MM/YYYY</option><option ${s.date_format === "MM/DD/YYYY" ? "selected" : ""}>MM/DD/YYYY</option></select></div><div class="setting-row"><div><strong>Decimal separator</strong><small>Number formatting preference.</small></div><select name="decimal_separator"><option value="." ${s.decimal_separator === "." ? "selected" : ""}>Period (.)</option><option value="," ${s.decimal_separator === "," ? "selected" : ""}>Comma (,)</option></select></div><div class="setting-row"><div><strong>Language</strong><small>Interface language.</small></div><select name="language"><option value="en" selected>English</option></select></div><button class="btn primary" style="margin-top:16px">Save preferences</button></form></section><section class="panel"><div class="panel-head"><div><h3>Change password</h3><p>Use at least 8 characters.</p></div></div><form id="passwordForm"><div class="field"><label>Current password</label><input name="current_password" type="password" required></div><div class="field"><label>New password</label><input name="new_password" type="password" minlength="8" required></div><button class="btn primary">Update password</button></form></section><section class="panel"><div class="panel-head"><div><h3>Data & privacy</h3><p>Your financial data belongs to your account.</p></div></div><p class="muted">Transactions, notes, categories, budgets, and vault records are scoped to your signed-in user. Passwords are hashed; vault entries use authenticated encryption.</p><button class="btn light" id="downloadData">Export transactions CSV</button></section></div>`;
  $("#profileForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/profile", {
        method: "PUT",
        body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
      });
      toast("Profile updated");
      await boot();
    } catch (x) {
      toast(x.message);
    }
  };
  $("#settingsForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const d = await api("/settings", {
        method: "PUT",
        body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
      });
      applyTheme(d.theme);
      toast("Preferences saved");
    } catch (x) {
      toast(x.message);
    }
  };
  $("#passwordForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/auth/password", {
        method: "PUT",
        body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
      });
      e.target.reset();
      toast("Password changed");
    } catch (x) {
      toast(x.message);
    }
  };
  $("#downloadData").onclick = async () =>
    downloadCsv(await api("/transactions"), "bluewallet-transactions.csv");
}
function downloadCsv(rows, filename) {
  if (!rows.length) {
    toast("No data to export");
    return;
  }
  const keys = Object.keys(rows[0]);
  const csv = [
    keys.join(","),
    ...rows.map((r) =>
      keys
        .map((k) => '"' + String(r[k] ?? "").replace(/"/g, '""') + '"')
        .join(","),
    ),
  ].join("\r\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
// Refresh the visible page after browser history navigation and initialize the app.
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});
setAuthMode("login");
boot();
