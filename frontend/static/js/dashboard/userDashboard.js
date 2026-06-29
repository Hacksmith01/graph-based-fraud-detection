import { requestJson } from "../api.js";
import { escapeHtml, formatCurrency, formatPercent, formatTime, setText } from "../utils.js";

export async function initUserDashboardPage() {
  await loadUserDashboard();
}

async function loadUserDashboard() {
  const result = await requestJson("/api/user/dashboard");
  if (result?.error) {
    window.location.href = "/login";
    return;
  }

  setText("userDashboardTitle", `Welcome, ${result.user.username}`);
  setText("userAccountText", `Account ID: ${result.user.account_id}`);
  setText("userTotalTransactions", result.metrics.total);
  setText("userFlaggedTransactions", result.metrics.flagged);
  setText("userPersonalRisk", `${result.metrics.personal_risk}%`);
  setText("userTotalSent", formatCurrency(result.metrics.total_sent));
  setText("userTotalReceived", formatCurrency(result.metrics.total_received));
  setText("userAverageAmount", formatCurrency(result.metrics.average_amount));
  setText("userRiskLevel", riskLevelFromScore(result.metrics.risk_score));
  renderUserTransactionTable(result.transactions);
  renderUserAlerts(result.alerts || []);
}

function renderUserTransactionTable(transactions) {
  const table = document.getElementById("userTransactionsTable");
  if (!table) {
    return;
  }

  if (!transactions.length) {
    table.innerHTML = '<tr><td colspan="9">No transactions yet. Submit one from the monitor page.</td></tr>';
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

function renderUserAlerts(alerts) {
  const list = document.getElementById("userAlertsList");
  if (!list) return;
  if (!alerts.length) {
    list.innerHTML = "<li>No recent alerts.</li>";
    return;
  }
  list.innerHTML = alerts.map((alert) => `
    <li><strong>${escapeHtml(alert.alert_type)}</strong><span>${escapeHtml(alert.message)}</span></li>
  `).join("");
}

function riskLevelFromScore(score) {
  if (score < 20) return "LOW";
  if (score < 50) return "MEDIUM";
  if (score < 80) return "HIGH";
  return "CRITICAL";
}
