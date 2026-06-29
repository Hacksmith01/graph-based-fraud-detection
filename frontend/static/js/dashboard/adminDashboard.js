import { requestJson } from "../api.js";
import { createModelChart } from "../charts.js";
import { escapeHtml, formatCurrency, formatPercent, formatTime, setText } from "../utils.js";

export function initAdminDashboard() {
  document.getElementById("refreshAdminButton").addEventListener("click", loadAdminTransactions);
  createModelChart();
}

export async function loadAdminTransactions() {
  const result = await requestJson("/api/admin/transactions");
  if (result?.error) {
    return;
  }

  setText("adminTotal", result.metrics.total);
  setText("adminFlagged", result.metrics.flagged);
  setText("adminAverageRisk", `${result.metrics.average_risk}%`);
  setText("adminTotalUsers", result.metrics.total_users);
  setText("adminActiveUsers", result.metrics.active_users);
  setText("adminFlaggedUsers", result.metrics.flagged_users);
  setText("adminFraudPercentage", `${result.metrics.fraud_percentage}%`);
  setText("adminAnomalyCount", result.metrics.anomaly_count);
  setText("modelF1", Number(result.model_validation?.f1_score || 0).toFixed(2));
  setText("modelRocAuc", Number(result.model_validation?.roc_auc || 0).toFixed(2));
  renderAdminTransactionTable(result.transactions);
  renderAdminAlerts(result.alerts || []);
  renderTopRiskyAccounts(result.top_risky_accounts || []);
  renderClusters(result.top_suspicious_clusters || []);
  renderFeatureImportance(result.feature_importance || []);
  renderAnalyticsCharts(result.analytics || {});
}

function renderAdminTransactionTable(transactions) {
  const table = document.getElementById("adminTransactionsTable");
  if (!table) {
    return;
  }

  if (!transactions.length) {
    table.innerHTML = '<tr><td colspan="10">No transactions submitted yet.</td></tr>';
    return;
  }

  table.innerHTML = transactions.map((transaction) => {
    const riskClass = transaction.fraud_prediction === 1 ? "risk-high" : "risk-low";
    const riskLevel = transaction.risk_level || "LOW";
    const predictionText = transaction.fraud_prediction === 1 ? "Fraud" : "Legitimate";

    return `
      <tr>
        <td>${escapeHtml(transaction.id)}</td>
        <td>${formatTime(transaction.timestamp)}</td>
        <td>${escapeHtml(transaction.sender)}</td>
        <td>${escapeHtml(transaction.receiver)}</td>
        <td>${escapeHtml(transaction.type)}</td>
        <td>${formatCurrency(transaction.amount)}</td>
        <td class="${riskClass}">${predictionText}</td>
        <td>${formatPercent(transaction.fraud_probability)}</td>
        <td class="risk-${riskLevel.toLowerCase()}">${escapeHtml(riskLevel)}</td>
        <td>${escapeHtml((transaction.explanation?.reasons || []).join(", "))}</td>
      </tr>
    `;
  }).join("");
}

function renderClusters(clusters) {
  const list = document.getElementById("suspiciousClustersList");
  if (!list) return;
  const suspicious = clusters.filter((cluster) => cluster.suspicious);
  if (!suspicious.length) {
    list.innerHTML = "<li>No suspicious clusters.</li>";
    return;
  }
  list.innerHTML = suspicious.map((cluster) => `
    <li><strong>Cluster ${cluster.cluster_id}: ${cluster.cluster_risk}% risk</strong>
    <span>${cluster.cluster_size} members: ${escapeHtml(cluster.members.slice(0, 6).join(", "))}</span></li>
  `).join("");
}

function renderFeatureImportance(features) {
  const list = document.getElementById("featureImportanceList");
  if (!list) return;
  if (!features.length) {
    list.innerHTML = "<li>Run model training to generate importance data.</li>";
    return;
  }
  list.innerHTML = features.slice(0, 8).map((item) => `
    <li><strong>${escapeHtml(item.feature)}</strong><span>${(Number(item.importance) * 100).toFixed(2)}%</span></li>
  `).join("");
}

const analyticsCharts = new Map();

function renderAnalyticsCharts(analytics) {
  renderTrendChart("fraudTrendChart", analytics.fraud_trend || [], "fraud", "Fraud", "#ff6b6b");
  renderTrendChart("alertTrendChart", analytics.alert_trend || [], "total", "Alerts", "#f5a623");
  renderTrendChart("userGrowthChart", analytics.user_growth || [], "total", "New users", "#44d19d");
  renderDistributionChart(analytics.transaction_distribution || []);
}

function renderTrendChart(id, rows, valueKey, label, color) {
  const canvas = document.getElementById(id);
  if (!canvas || !window.Chart) return;
  analyticsCharts.get(id)?.destroy();
  analyticsCharts.set(id, new Chart(canvas, {
    type: "line",
    data: { labels: rows.map((row) => row.date), datasets: [{ label, data: rows.map((row) => row[valueKey]), borderColor: color, tension: 0.3 }] },
    options: { responsive: true, plugins: { legend: { labels: { color: "#edf2f6" } } } }
  }));
}

function renderDistributionChart(rows) {
  const id = "transactionDistributionChart";
  const canvas = document.getElementById(id);
  if (!canvas || !window.Chart) return;
  analyticsCharts.get(id)?.destroy();
  analyticsCharts.set(id, new Chart(canvas, {
    type: "doughnut",
    data: { labels: rows.map((row) => row.label), datasets: [{ data: rows.map((row) => row.total), backgroundColor: ["#5eb1ff", "#44d19d", "#f5a623", "#ff6b6b", "#9d4edd"] }] },
    options: { responsive: true, plugins: { legend: { labels: { color: "#edf2f6" } } } }
  }));
}

function renderAdminAlerts(alerts) {
  const list = document.getElementById("adminAlertsList");
  if (!list) {
    return;
  }

  if (!alerts.length) {
    list.innerHTML = "<li>No alerts yet.</li>";
    return;
  }

  list.innerHTML = alerts.slice(0, 8).map((alert) => `
    <li>
      <strong>${escapeHtml(alert.alert_type)}</strong>
      <span>${escapeHtml(alert.message)}</span>
    </li>
  `).join("");
}

function renderTopRiskyAccounts(accounts) {
  const list = document.getElementById("topRiskyAccounts");
  if (!list) {
    return;
  }

  if (!accounts.length) {
    list.innerHTML = "<li>No risky accounts yet.</li>";
    return;
  }

  list.innerHTML = accounts.map((account) => `
    <li>
      <strong>${escapeHtml(account.account_id)}</strong>
      <span>${formatPercent(account.average_probability)} average risk across ${account.total} transaction(s)</span>
    </li>
  `).join("");
}

