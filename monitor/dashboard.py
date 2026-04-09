from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional

from aiohttp import web

from .store import JsonlStore, parse_since_expression, parse_timestamp


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ollama Monitor</title>
  <style>
    :root {
      --bg: #ffffff;
      --text: #5b6270;
      --text-strong: #242938;
      --line: #e6e8ef;
      --line-soft: #f0f2f7;
      --blue: #1f83f2;
      --blue-soft: rgba(31, 131, 242, 0.12);
      --chip: #f7f8fb;
      --shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
      --ok: #198754;
      --err: #c0392b;
      --radius: 18px;
      --font: "Inter", "Avenir Next", "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: var(--font);
    }

    .page {
      width: min(1700px, calc(100vw - 48px));
      margin: 0 auto;
      padding: 20px 0 32px;
    }

    .toolbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }

    .range-row,
    .action-row {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .toolbar-label {
      color: var(--text);
      font-size: 14px;
    }

    .date-wrap {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .date-input,
    .search-input,
    .select-input,
    .btn {
      height: 46px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fff;
      padding: 0 16px;
      color: var(--text-strong);
      font-size: 15px;
      outline: none;
      transition: border-color 140ms ease, box-shadow 140ms ease, background 140ms ease;
    }

    .date-input:focus,
    .search-input:focus,
    .select-input:focus,
    .btn:hover {
      border-color: #c9d6ef;
      box-shadow: 0 0 0 4px rgba(31, 131, 242, 0.08);
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #fff;
      color: var(--text);
      cursor: pointer;
      user-select: none;
    }

    .btn:disabled {
      cursor: not-allowed;
      opacity: 0.48;
      box-shadow: none;
    }

    .btn.primary {
      color: var(--blue);
      border-color: #d9e7fb;
      background: #f8fbff;
    }

    .search-input {
      width: 180px;
    }

    .filters-panel {
      display: none;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fff;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }

    .filters-panel.open {
      display: flex;
    }

    .filters-left,
    .filters-right {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }

    .meta-text {
      font-size: 13px;
      color: #80879a;
    }

    .chart-shell {
      position: relative;
      padding: 10px 4px 24px;
      margin-bottom: 12px;
    }

    .chart-top {
      display: flex;
      justify-content: flex-end;
      align-items: flex-end;
      margin-bottom: 10px;
      color: var(--text);
      font-size: 14px;
      min-height: 24px;
    }

    .chart-req {
      color: var(--text-strong);
      font-weight: 600;
    }

    .chart-area {
      display: flex;
      align-items: flex-end;
      gap: 22px;
      min-height: 150px;
      padding: 6px 10px 0 12px;
    }

    .chart-col {
      flex: 1;
      min-width: 52px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      outline: none;
    }

    .chart-metrics {
      min-height: 38px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-end;
      gap: 2px;
      text-align: center;
    }

    .chart-req-label {
      color: var(--text-strong);
      font-size: 13px;
      font-weight: 600;
      line-height: 1.1;
      font-variant-numeric: tabular-nums;
    }

    .chart-tps-label {
      color: #7c8396;
      font-size: 11px;
      line-height: 1.1;
      font-variant-numeric: tabular-nums;
    }

    .chart-bar-wrap {
      height: 92px;
      width: 100%;
      display: flex;
      align-items: flex-end;
      justify-content: center;
    }

    .chart-bar {
      width: min(100%, 88px);
      min-height: 4px;
      border-radius: 0;
      background: var(--blue);
      transition: transform 140ms ease, box-shadow 140ms ease, opacity 140ms ease;
    }

    .chart-col.is-active .chart-bar,
    .chart-col:hover .chart-bar {
      transform: translateY(-2px);
      box-shadow: 0 14px 28px rgba(31, 131, 242, 0.22);
      opacity: 0.96;
    }

    .chart-label {
      font-size: 12px;
      color: #7c8396;
      text-align: center;
      line-height: 1.35;
      white-space: nowrap;
    }

    .chart-tooltip {
      position: fixed;
      min-width: 180px;
      max-width: 240px;
      padding: 14px 15px;
      border-radius: 16px;
      border: 1px solid rgba(213, 220, 235, 0.92);
      background: rgba(255, 255, 255, 0.98);
      box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
      backdrop-filter: blur(10px);
      pointer-events: none;
      z-index: 40;
      opacity: 0;
      transform: translateY(6px);
      transition: opacity 120ms ease, transform 120ms ease;
    }

    .chart-tooltip.open {
      opacity: 1;
      transform: translateY(0);
    }

    .chart-tooltip-title {
      color: var(--text-strong);
      font-size: 13px;
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 10px;
    }

    .chart-tooltip-grid {
      display: grid;
      gap: 8px;
    }

    .chart-tooltip-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }

    .chart-tooltip-key {
      color: #8a90a3;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .chart-tooltip-value {
      color: var(--text-strong);
      font-size: 13px;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
    }

    .table-card {
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: #fff;
      box-shadow: var(--shadow);
    }

    .table-wrap {
      overflow: auto;
    }

    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      padding: 14px 18px;
      border-top: 1px solid var(--line-soft);
      background: #fff;
    }

    .pagination-text {
      color: #7c8396;
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }

    .pagination-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .pagination-page {
      color: var(--text-strong);
      font-size: 13px;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      min-width: 78px;
      text-align: center;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 1200px;
    }

    thead th {
      background: #fff;
      color: #6e7487;
      font-weight: 500;
      font-size: 14px;
      text-align: left;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      border-right: 1px solid var(--line-soft);
      white-space: nowrap;
    }

    thead th:last-child,
    tbody td:last-child {
      border-right: none;
    }

    tbody td {
      padding: 16px 18px;
      border-bottom: 1px solid var(--line-soft);
      border-right: 1px solid var(--line-soft);
      font-size: 15px;
      color: var(--text);
      vertical-align: middle;
      white-space: nowrap;
    }

    tbody tr:hover {
      background: #fafbfe;
    }

    .provider-cell {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 220px;
    }

    .provider-badge {
      width: 34px;
      height: 34px;
      border-radius: 12px;
      background: #f6f7fb;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--blue);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      border: 1px solid var(--line-soft);
    }

    .model-link {
      color: #6874f6;
      text-decoration: underline;
      text-underline-offset: 2px;
      cursor: pointer;
      max-width: 240px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      display: inline-block;
    }

    .muted {
      color: #8a90a3;
    }

    .tokens,
    .speed,
    .mono {
      font-variant-numeric: tabular-nums;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      background: #f5f7fb;
      color: #6e7487;
    }

    .status-pill.ok {
      background: rgba(25, 135, 84, 0.1);
      color: var(--ok);
    }

    .status-pill.err {
      background: rgba(192, 57, 43, 0.1);
      color: var(--err);
    }

    .action-btn {
      border: 1px solid var(--line);
      background: #fff;
      color: #6e7487;
      height: 36px;
      padding: 0 12px;
      border-radius: 12px;
      cursor: pointer;
    }

    .empty {
      padding: 42px 20px;
      text-align: center;
      color: #8a90a3;
    }

    .dialog {
      position: fixed;
      inset: 0;
      background: rgba(20, 24, 32, 0.34);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
      z-index: 20;
    }

    .dialog.open {
      display: flex;
    }

    .dialog-card {
      width: min(760px, 100%);
      max-height: 84vh;
      overflow: auto;
      background: #fff;
      border-radius: 20px;
      border: 1px solid var(--line);
      box-shadow: 0 24px 80px rgba(15, 23, 42, 0.18);
      padding: 22px;
    }

    .dialog-top {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 16px;
    }

    .dialog-title {
      margin: 0;
      font-size: 20px;
      color: var(--text-strong);
    }

    .dialog-close {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 12px;
      width: 38px;
      height: 38px;
      cursor: pointer;
      color: #7a8090;
      font-size: 18px;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }

    .detail-item {
      border: 1px solid var(--line-soft);
      border-radius: 14px;
      padding: 12px 14px;
      background: #fafbfe;
    }

    .detail-key {
      font-size: 12px;
      color: #8a90a3;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 6px;
    }

    .detail-value {
      color: var(--text-strong);
      word-break: break-word;
      font-size: 14px;
      font-weight: 600;
    }

    .detail-block {
      border: 1px solid var(--line-soft);
      border-radius: 14px;
      padding: 14px;
      background: #fafbfe;
      margin-bottom: 12px;
    }

    .detail-block h3 {
      margin: 0 0 8px;
      font-size: 12px;
      color: #8a90a3;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .detail-pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      color: var(--text-strong);
      font-family: "SFMono-Regular", "Consolas", monospace;
      font-size: 12px;
      line-height: 1.55;
    }

    @media (max-width: 980px) {
      .page {
        width: min(100vw - 20px, 100%);
      }

      .detail-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="toolbar">
      <div class="range-row">
        <div class="date-wrap">
          <span class="toolbar-label">From:</span>
          <input class="date-input" type="datetime-local" id="fromInput">
        </div>
        <div class="date-wrap">
          <span class="toolbar-label">To:</span>
          <input class="date-input" type="datetime-local" id="toInput">
        </div>
      </div>
      <div class="action-row">
        <button class="btn" type="button" id="filtersBtn">Filters</button>
        <button class="btn" type="button" id="refreshBtn">Refresh</button>
        <button class="btn primary" type="button" id="exportBtn">Export</button>
        <input class="search-input" id="searchInput" type="search" placeholder="Find">
      </div>
    </div>

    <div class="filters-panel" id="filtersPanel">
      <div class="filters-left">
        <select class="select-input" id="modelSelect">
          <option value="">All models</option>
        </select>
      </div>
      <div class="filters-right">
        <span class="meta-text" id="metaProxy">Proxy: -</span>
        <span class="meta-text" id="metaUpstream">Upstream: -</span>
        <span class="meta-text" id="metaUpdated">Updated: -</span>
      </div>
    </div>

    <div class="chart-shell">
      <div class="chart-top">
        <span class="chart-req" id="requestCount">0 req</span>
      </div>
      <div class="chart-area" id="chartArea"></div>
      <div class="chart-tooltip" id="chartTooltip"></div>
    </div>

    <div class="table-card">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Provider / Model</th>
              <th>App</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Usage</th>
              <th>Speed</th>
              <th>Finish</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="tableBody"></tbody>
        </table>
      </div>
      <div class="pagination-bar">
        <span class="pagination-text" id="paginationText">Showing 0-0 of 0</span>
        <div class="pagination-actions">
          <button class="btn" type="button" id="prevPageBtn">Prev</button>
          <span class="pagination-page" id="paginationPage">Page 1 / 1</span>
          <button class="btn" type="button" id="nextPageBtn">Next</button>
        </div>
      </div>
    </div>
  </div>

  <div class="dialog" id="detailDialog">
    <div class="dialog-card">
      <div class="dialog-top">
        <div>
          <h2 class="dialog-title">Request details</h2>
          <div class="muted">Stored metadata only. Prompt and response content are not saved.</div>
        </div>
        <button class="dialog-close" type="button" id="dialogClose">x</button>
      </div>
      <div id="detailContent"></div>
    </div>
  </div>

  <script>
    const state = {
      model: "",
      q: "",
      from: "",
      to: "",
      defaultSince: "7d",
      customRange: false,
      page: 1,
      pageSize: 10,
      refreshDelayMs: 30000,
      refreshInFlight: false,
      timer: null,
      recordsById: new Map()
    };

    const refs = {
      fromInput: document.getElementById("fromInput"),
      toInput: document.getElementById("toInput"),
      filtersBtn: document.getElementById("filtersBtn"),
      refreshBtn: document.getElementById("refreshBtn"),
      exportBtn: document.getElementById("exportBtn"),
      searchInput: document.getElementById("searchInput"),
      filtersPanel: document.getElementById("filtersPanel"),
      modelSelect: document.getElementById("modelSelect"),
      metaProxy: document.getElementById("metaProxy"),
      metaUpstream: document.getElementById("metaUpstream"),
      metaUpdated: document.getElementById("metaUpdated"),
      requestCount: document.getElementById("requestCount"),
      chartArea: document.getElementById("chartArea"),
      chartTooltip: document.getElementById("chartTooltip"),
      tableBody: document.getElementById("tableBody"),
      paginationText: document.getElementById("paginationText"),
      paginationPage: document.getElementById("paginationPage"),
      prevPageBtn: document.getElementById("prevPageBtn"),
      nextPageBtn: document.getElementById("nextPageBtn"),
      detailDialog: document.getElementById("detailDialog"),
      detailContent: document.getElementById("detailContent"),
      dialogClose: document.getElementById("dialogClose")
    };

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function formatNumber(value) {
      if (value === null || value === undefined) return "-";
      return new Intl.NumberFormat().format(value);
    }

    function formatDecimal(value, suffix = "") {
      if (value === null || value === undefined) return "-";
      return `${Number(value).toFixed(1)}${suffix}`;
    }

    function formatTimestamp(value) {
      if (!value) return "-";
      const date = new Date(value);
      return new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit"
      }).format(date);
    }

    function updateMetaUpdated(generatedAt, note = "") {
      const updatedText = generatedAt
        ? new Date(generatedAt).toLocaleTimeString()
        : "-";
      const detail = note || `auto refresh ${Math.round(state.refreshDelayMs / 1000)}s`;
      refs.metaUpdated.textContent = `Updated: ${updatedText} · ${detail}`;
    }

    function updateModelOptions(models) {
      const current = state.model;
      refs.modelSelect.innerHTML = `<option value="">All models</option>` + models
        .map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`)
        .join("");
      refs.modelSelect.value = current;
    }

    function buildQuery(extra = {}) {
      const params = new URLSearchParams();
      if (state.customRange) {
        if (state.from) params.set("from", state.from);
        if (state.to) params.set("to", state.to);
      } else {
        params.set("since", state.defaultSince);
      }
      params.set("page", String(extra.page || state.page));
      params.set("page_size", String(extra.pageSize || state.pageSize));
      if (state.model) params.set("model", state.model);
      if (state.q) params.set("q", state.q);
      for (const [key, value] of Object.entries(extra)) {
        if (key === "page" || key === "pageSize") {
          continue;
        }
        if (value !== undefined && value !== null) {
          params.set(key, String(value));
        }
      }
      return params;
    }

    function renderChart(buckets) {
      if (!buckets.length) {
        hideChartTooltip();
        refs.chartArea.innerHTML = `<div class="empty">No request data in this range.</div>`;
        return;
      }

      const max = Math.max(...buckets.map((item) => item.count), 1);
      refs.chartArea.innerHTML = buckets.map((bucket) => {
        const height = Math.max(6, Math.round((bucket.count / max) * 92));
        return `
          <div class="chart-col" tabindex="0" aria-label="${escapeHtml(`${bucket.label}, ${bucket.req_label}, total tokens ${bucket.total_tokens_label}, ${bucket.tps_label}, ${bucket.success_label}`)}">
            <div class="chart-metrics">
              <div class="chart-req-label">${escapeHtml(bucket.req_label)}</div>
              <div class="chart-tps-label">${escapeHtml(bucket.tps_label)}</div>
            </div>
            <div class="chart-bar-wrap">
              <div class="chart-bar" style="height:${height}px"></div>
            </div>
            <div class="chart-label">${escapeHtml(bucket.label)}</div>
          </div>
        `;
      }).join("");

      refs.chartArea.querySelectorAll(".chart-col").forEach((node, index) => {
        const bucket = buckets[index];
        node.addEventListener("mouseenter", (event) => showChartTooltip(bucket, node, event));
        node.addEventListener("mousemove", (event) => positionChartTooltip(event.clientX, event.clientY));
        node.addEventListener("mouseleave", () => hideChartTooltip(node));
        node.addEventListener("focus", () => showChartTooltip(bucket, node));
        node.addEventListener("blur", () => hideChartTooltip(node));
      });
    }

    function renderChartTooltip(bucket) {
      refs.chartTooltip.innerHTML = `
        <div class="chart-tooltip-title">${escapeHtml(bucket.tooltip_title)}</div>
        <div class="chart-tooltip-grid">
          <div class="chart-tooltip-row">
            <span class="chart-tooltip-key">req</span>
            <span class="chart-tooltip-value">${escapeHtml(bucket.req_label)}</span>
          </div>
          <div class="chart-tooltip-row">
            <span class="chart-tooltip-key">total tokens</span>
            <span class="chart-tooltip-value">${escapeHtml(bucket.total_tokens_label)}</span>
          </div>
          <div class="chart-tooltip-row">
            <span class="chart-tooltip-key">avg tps</span>
            <span class="chart-tooltip-value">${escapeHtml(bucket.tps_label_value)}</span>
          </div>
          <div class="chart-tooltip-row">
            <span class="chart-tooltip-key">success rate</span>
            <span class="chart-tooltip-value">${escapeHtml(bucket.success_label_value)}</span>
          </div>
        </div>
      `;
    }

    function positionChartTooltip(clientX, clientY) {
      const tooltip = refs.chartTooltip;
      const margin = 14;
      const width = tooltip.offsetWidth || 200;
      const height = tooltip.offsetHeight || 120;

      let left = clientX + 18;
      let top = clientY - height - 18;

      if (left + width > window.innerWidth - margin) {
        left = window.innerWidth - width - margin;
      }
      if (top < margin) {
        top = clientY + 18;
      }

      tooltip.style.left = `${Math.max(margin, left)}px`;
      tooltip.style.top = `${Math.max(margin, top)}px`;
    }

    function showChartTooltip(bucket, node, event = null) {
      renderChartTooltip(bucket);
      refs.chartTooltip.classList.add("open");
      refs.chartArea.querySelectorAll(".chart-col.is-active").forEach((activeNode) => {
        if (activeNode !== node) activeNode.classList.remove("is-active");
      });
      node.classList.add("is-active");

      if (event) {
        positionChartTooltip(event.clientX, event.clientY);
        return;
      }

      const rect = node.getBoundingClientRect();
      positionChartTooltip(rect.left + rect.width / 2, rect.top);
    }

    function hideChartTooltip(node = null) {
      refs.chartTooltip.classList.remove("open");
      if (node) {
        node.classList.remove("is-active");
        return;
      }
      refs.chartArea.querySelectorAll(".chart-col.is-active").forEach((activeNode) => {
        activeNode.classList.remove("is-active");
      });
    }

    function renderTable(records) {
      if (!records.length) {
        refs.tableBody.innerHTML = `<tr><td colspan="9"><div class="empty">No requests recorded for this range.</div></td></tr>`;
        return;
      }

      refs.tableBody.innerHTML = records.map((record) => `
        <tr>
          <td>${escapeHtml(record.timestamp_label)}</td>
          <td>
            <div class="provider-cell">
              <span class="provider-badge">ol</span>
              <span class="model-link" data-view-id="${escapeHtml(record.request_id)}">${escapeHtml(record.model || "-")}</span>
            </div>
          </td>
          <td>${escapeHtml(record.app_label)}</td>
          <td class="tokens">${escapeHtml(record.tokens_label)}</td>
          <td>${escapeHtml(record.cost_label)}</td>
          <td>${escapeHtml(record.usage_label)}</td>
          <td class="speed">${escapeHtml(record.speed_label)}</td>
          <td>${escapeHtml(record.finish_label)}</td>
          <td><button class="action-btn" type="button" data-view-id="${escapeHtml(record.request_id)}">View</button></td>
        </tr>
      `).join("");

      refs.tableBody.querySelectorAll("[data-view-id]").forEach((node) => {
        node.addEventListener("click", () => openDetail(node.dataset.viewId));
      });
    }

    function renderPagination(pagination) {
      refs.paginationText.textContent =
        `Showing ${pagination.start_index}-${pagination.end_index} of ${formatNumber(pagination.total_records)}`;
      refs.paginationPage.textContent = `Page ${pagination.page} / ${pagination.page_count}`;
      refs.prevPageBtn.disabled = !pagination.has_prev;
      refs.nextPageBtn.disabled = !pagination.has_next;
    }

    function openDetail(requestId) {
      const record = state.recordsById.get(requestId);
      if (!record) return;
      refs.detailContent.innerHTML = `
        <div class="detail-grid">
          <div class="detail-item"><div class="detail-key">Timestamp</div><div class="detail-value">${escapeHtml(record.timestamp)}</div></div>
          <div class="detail-item"><div class="detail-key">Request ID</div><div class="detail-value">${escapeHtml(record.request_id)}</div></div>
          <div class="detail-item"><div class="detail-key">Model</div><div class="detail-value">${escapeHtml(record.model || "-")}</div></div>
          <div class="detail-item"><div class="detail-key">Path</div><div class="detail-value">${escapeHtml(record.path)}</div></div>
          <div class="detail-item"><div class="detail-key">Status</div><div class="detail-value">${escapeHtml(record.status_label)}</div></div>
          <div class="detail-item"><div class="detail-key">Client IP</div><div class="detail-value">${escapeHtml(record.client_ip || "-")}</div></div>
          <div class="detail-item"><div class="detail-key">Prompt Tokens</div><div class="detail-value">${formatNumber(record.prompt_tokens)}</div></div>
          <div class="detail-item"><div class="detail-key">Completion Tokens</div><div class="detail-value">${formatNumber(record.completion_tokens)}</div></div>
          <div class="detail-item"><div class="detail-key">Total Tokens</div><div class="detail-value">${formatNumber(record.total_tokens)}</div></div>
          <div class="detail-item"><div class="detail-key">Speed</div><div class="detail-value">${escapeHtml(record.speed_label)}</div></div>
          <div class="detail-item"><div class="detail-key">Total Latency</div><div class="detail-value">${formatDecimal(record.total_ms, " ms")}</div></div>
          <div class="detail-item"><div class="detail-key">Finish</div><div class="detail-value">${escapeHtml(record.finish_label)}</div></div>
        </div>
        <div class="detail-block">
          <h3>Timing</h3>
          <pre class="detail-pre">load_ms        : ${formatDecimal(record.load_ms, " ms")}
prompt_eval_ms : ${formatDecimal(record.prompt_eval_ms, " ms")}
eval_ms        : ${formatDecimal(record.eval_ms, " ms")}</pre>
        </div>
        <div class="detail-block">
          <h3>Error</h3>
          <pre class="detail-pre">${escapeHtml(record.error || "None")}</pre>
        </div>
      `;
      refs.detailDialog.classList.add("open");
    }

    function closeDetail() {
      refs.detailDialog.classList.remove("open");
    }

    function syncStateFromControls() {
      state.model = refs.modelSelect.value || "";
      state.q = refs.searchInput.value.trim();
    }

    async function loadData() {
      syncStateFromControls();
      const response = await fetch(`/ui/api/overview?${buildQuery().toString()}`, {
        cache: "no-store"
      });
      if (!response.ok) throw new Error(`Dashboard API returned ${response.status}`);
      const data = await response.json();

      if (!state.customRange) {
        state.from = data.filters.from_local;
        state.to = data.filters.to_local;
      }
      refs.fromInput.value = state.from;
      refs.toInput.value = state.to;
      refs.metaProxy.textContent = `Proxy: ${data.meta.proxy}`;
      refs.metaUpstream.textContent = `Upstream: ${data.meta.upstream}`;
      updateMetaUpdated(data.meta.generated_at);
      refs.requestCount.textContent = `~${formatNumber(data.summary.request_count)} req`;
      state.page = data.pagination.page;

      updateModelOptions(data.filters.available_models);
      renderChart(data.chart.buckets);
      renderTable(data.recent);
      renderPagination(data.pagination);

      state.recordsById = new Map();
      data.recent.forEach((record) => state.recordsById.set(record.request_id, record));
      updateExportUrl();
    }

    function updateExportUrl() {
      syncStateFromControls();
      refs.exportBtn.dataset.href = `/ui/api/export.csv?${buildQuery({ limit: 2000 }).toString()}`;
    }

    let searchTimer = null;
    function queueRefresh(delay = 180) {
      if (searchTimer) window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        refreshNow().catch(() => {});
      }, delay);
    }

    function scheduleAutoRefresh() {
      if (state.timer) window.clearTimeout(state.timer);
      state.timer = window.setTimeout(() => {
        refreshNow().catch(() => {});
      }, state.refreshDelayMs);
    }

    async function refreshNow() {
      if (state.refreshInFlight) {
        return;
      }
      state.refreshInFlight = true;
      const originalLabel = refs.refreshBtn.textContent;
      refs.refreshBtn.textContent = "Refreshing...";
      refs.refreshBtn.disabled = true;
      try {
        await loadData();
      } catch (error) {
        updateMetaUpdated(null, `refresh failed: ${error.message}`);
      } finally {
        state.refreshInFlight = false;
        refs.refreshBtn.disabled = false;
        refs.refreshBtn.textContent = originalLabel;
        scheduleAutoRefresh();
      }
    }

    refs.filtersBtn.addEventListener("click", () => {
      refs.filtersPanel.classList.toggle("open");
    });

    refs.refreshBtn.addEventListener("click", () => {
      refreshNow();
    });

    refs.exportBtn.addEventListener("click", () => {
      updateExportUrl();
      window.location.href = refs.exportBtn.dataset.href;
    });

    refs.searchInput.addEventListener("input", (event) => {
      state.q = event.target.value.trim();
      state.page = 1;
      queueRefresh();
    });

    refs.modelSelect.addEventListener("change", (event) => {
      state.model = event.target.value;
      state.page = 1;
      refreshNow();
    });

    refs.fromInput.addEventListener("change", (event) => {
      state.from = event.target.value;
      state.customRange = true;
      state.page = 1;
      queueRefresh();
    });

    refs.toInput.addEventListener("change", (event) => {
      state.to = event.target.value;
      state.customRange = true;
      state.page = 1;
      queueRefresh();
    });

    refs.prevPageBtn.addEventListener("click", () => {
      if (state.page <= 1) return;
      state.page -= 1;
      refreshNow();
    });

    refs.nextPageBtn.addEventListener("click", () => {
      state.page += 1;
      refreshNow();
    });

    refs.dialogClose.addEventListener("click", closeDetail);
    refs.detailDialog.addEventListener("click", (event) => {
      if (event.target === refs.detailDialog) closeDetail();
    });

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        refreshNow().catch(() => {});
      }
    });

    refreshNow().catch((error) => {
      updateMetaUpdated(null, `initial load failed: ${error.message}`);
    });
  </script>
</body>
</html>
"""


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _parse_local_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_now().tzinfo)
    return parsed.astimezone()


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(mean(values), 2)


def _bucket_label(timestamp: datetime, bucket_by_day: bool) -> str:
    return timestamp.strftime("%b %-d" if bucket_by_day else "%b %-d, %-I:%M %p")


def _bucket_tooltip(timestamp: datetime, bucket_by_day: bool) -> str:
    return timestamp.strftime("%a, %b %-d" if bucket_by_day else "%a, %b %-d %I:%M %p")


def _build_buckets(records: List[Dict[str, Any]], start_dt: datetime, end_dt: datetime) -> List[Dict[str, Any]]:
    bucket_by_day = (end_dt - start_dt) > timedelta(hours=48)
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "tps_values": [], "success_count": 0, "total_tokens": 0}
    )
    for record in records:
        stamp = parse_timestamp(record["timestamp"]).astimezone()
        key = stamp.strftime("%Y-%m-%d") if bucket_by_day else stamp.strftime("%Y-%m-%d %H:00")
        buckets[key]["count"] += 1
        if record.get("success"):
            buckets[key]["success_count"] += 1
        buckets[key]["total_tokens"] += int(record.get("total_tokens") or 0)
        if record.get("tps") is not None:
            buckets[key]["tps_values"].append(float(record["tps"]))

    rows = []
    for key in sorted(buckets):
        stamp = datetime.strptime(key, "%Y-%m-%d" if bucket_by_day else "%Y-%m-%d %H:00")
        stamp = stamp.replace(tzinfo=start_dt.tzinfo)
        avg_tps = _safe_mean(buckets[key]["tps_values"])
        success_rate = round((buckets[key]["success_count"] / buckets[key]["count"]) * 100, 1)
        rows.append(
            {
                "label": _bucket_label(stamp, bucket_by_day),
                "tooltip_title": _bucket_tooltip(stamp, bucket_by_day),
                "count": buckets[key]["count"],
                "avg_tps": avg_tps,
                "success_rate": success_rate,
                "req_label": f"{buckets[key]['count']:,} req",
                "total_tokens_label": f"{buckets[key]['total_tokens']:,}",
                "tps_label": f"avg {avg_tps:.1f} tps" if avg_tps is not None else "avg -",
                "tps_label_value": f"{avg_tps:.1f} tps" if avg_tps is not None else "-",
                "success_label": f"ok {success_rate:.1f}%",
                "success_label_value": f"{success_rate:.1f}%",
            }
        )
    return rows


def _format_timestamp_label(value: str) -> str:
    stamp = parse_timestamp(value).astimezone()
    return stamp.strftime("%b %-d, %-I:%M %p")


def _build_recent_rows(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for record in records:
        row = dict(record)
        row["timestamp_label"] = _format_timestamp_label(record["timestamp"])
        row["tokens_label"] = f"{int(record.get('prompt_tokens') or 0):,} -> {int(record.get('completion_tokens') or 0):,}"
        row["speed_label"] = f"{float(record['tps']):.1f} tps" if record.get("tps") is not None else "-"
        row["finish_label"] = record.get("done_reason") or "-"
        row["status_label"] = f"{record.get('status_code', '-')}/{'ok' if record.get('success') else 'err'}"
        row["app_label"] = "Local Proxy"
        row["cost_label"] = "$ 0.00"
        row["usage_label"] = "Local"
        rows.append(row)
    return rows


def _filter_records(
    records: List[Dict[str, Any]],
    *,
    end_dt: datetime,
    query: Optional[str],
) -> List[Dict[str, Any]]:
    filtered = []
    needle = (query or "").strip().lower()
    for record in records:
        stamp = parse_timestamp(record["timestamp"]).astimezone()
        if stamp > end_dt:
            continue
        if needle:
            haystack = " ".join(
                str(record.get(field) or "")
                for field in ("timestamp", "model", "path", "done_reason", "error", "status_code")
            ).lower()
            if needle not in haystack:
                continue
        filtered.append(record)
    return filtered


def _paginate_recent_records(
    records: List[Dict[str, Any]],
    *,
    page: int,
    page_size: int,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    newest_first = list(reversed(records))
    total_records = len(newest_first)
    page_count = max(1, (total_records + page_size - 1) // page_size) if total_records else 1
    current_page = min(max(1, page), page_count)
    start = (current_page - 1) * page_size
    end = start + page_size
    page_records = newest_first[start:end]

    if total_records == 0:
        start_index = 0
        end_index = 0
    else:
        start_index = start + 1
        end_index = min(start + len(page_records), total_records)

    pagination = {
        "page": current_page,
        "page_size": page_size,
        "page_count": page_count,
        "total_records": total_records,
        "start_index": start_index,
        "end_index": end_index,
        "has_prev": current_page > 1,
        "has_next": current_page < page_count,
    }
    return page_records, pagination


def build_overview_payload(
    *,
    records: List[Dict[str, Any]],
    start_dt: datetime,
    end_dt: datetime,
    model: Optional[str],
    query: Optional[str],
    page: int,
    page_size: int,
    available_models: List[str],
    proxy_label: str,
    upstream_label: str,
) -> Dict[str, Any]:
    now = _local_now()
    total_ms_values = [float(record["total_ms"]) for record in records if record.get("total_ms") is not None]
    tps_values = [float(record["tps"]) for record in records if record.get("tps") is not None]
    success_count = sum(1 for record in records if record.get("success"))
    recent_page_records, pagination = _paginate_recent_records(records, page=page, page_size=page_size)

    return {
        "meta": {
            "generated_at": now.isoformat(),
            "proxy": proxy_label,
            "upstream": upstream_label,
        },
        "filters": {
            "from": start_dt.isoformat(),
            "to": end_dt.isoformat(),
            "from_local": start_dt.strftime("%Y-%m-%dT%H:%M"),
            "to_local": end_dt.strftime("%Y-%m-%dT%H:%M"),
            "model": model,
            "q": query or "",
            "available_models": available_models,
        },
        "summary": {
            "request_count": len(records),
            "success_rate": round((success_count / len(records)) * 100, 1) if records else 0.0,
            "total_tokens": sum(int(record.get("total_tokens") or 0) for record in records),
            "avg_total_ms": _safe_mean(total_ms_values),
            "avg_tps": _safe_mean(tps_values),
        },
        "chart": {
            "buckets": _build_buckets(records, start_dt=start_dt, end_dt=end_dt),
        },
        "pagination": pagination,
        "recent": _build_recent_rows(recent_page_records),
    }


def _records_to_csv(records: List[Dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "timestamp",
            "model",
            "path",
            "status_code",
            "success",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "total_ms",
            "load_ms",
            "prompt_eval_ms",
            "eval_ms",
            "tps",
            "done_reason",
            "error",
            "client_ip",
        ]
    )
    for record in records:
        writer.writerow(
            [
                record.get("timestamp"),
                record.get("model"),
                record.get("path"),
                record.get("status_code"),
                record.get("success"),
                record.get("prompt_tokens"),
                record.get("completion_tokens"),
                record.get("total_tokens"),
                record.get("total_ms"),
                record.get("load_ms"),
                record.get("prompt_eval_ms"),
                record.get("eval_ms"),
                record.get("tps"),
                record.get("done_reason"),
                record.get("error"),
                record.get("client_ip"),
            ]
        )
    return buffer.getvalue()


class DashboardService:
    def __init__(self, log_dir: Any, proxy_label: str, upstream_label: str) -> None:
        self.store = JsonlStore(log_dir)
        self.proxy_label = proxy_label
        self.upstream_label = upstream_label

    def _resolve_window(self, request: web.Request) -> tuple[datetime, datetime]:
        now = _local_now()
        from_raw = request.query.get("from")
        to_raw = request.query.get("to")

        if from_raw or to_raw:
            end_dt = _parse_local_datetime(to_raw) if to_raw else now
            start_dt = _parse_local_datetime(from_raw) if from_raw else end_dt - timedelta(days=7)
        else:
            since = request.query.get("since", "7d")
            start_dt = parse_since_expression(since, now=now)
            end_dt = now

        if start_dt > end_dt:
            raise web.HTTPBadRequest(text="'from' must be earlier than 'to'.")
        return start_dt, end_dt

    def _load_filtered_records(
        self,
        request: web.Request,
        *,
        limit_cap: int,
    ) -> tuple[List[Dict[str, Any]], datetime, datetime, Optional[str], Optional[str], int, int]:
        start_dt, end_dt = self._resolve_window(request)
        model = request.query.get("model") or None
        query = request.query.get("q") or None
        limit_raw = request.query.get("limit", "120")
        page_raw = request.query.get("page", "1")
        page_size_raw = request.query.get("page_size", "10")
        try:
            limit = max(1, min(limit_cap, int(limit_raw)))
        except ValueError as exc:
            raise web.HTTPBadRequest(text=f"Invalid limit: {limit_raw!r}") from exc
        try:
            page = max(1, int(page_raw))
        except ValueError as exc:
            raise web.HTTPBadRequest(text=f"Invalid page: {page_raw!r}") from exc
        try:
            page_size = max(1, min(100, int(page_size_raw)))
        except ValueError as exc:
            raise web.HTTPBadRequest(text=f"Invalid page_size: {page_size_raw!r}") from exc

        records = self.store.query_records(since=start_dt, model=model, newest_first=False)
        records = _filter_records(records, end_dt=end_dt, query=query)
        return records, start_dt, end_dt, model, query, limit, page, page_size

    async def handle_page(self, _request: web.Request) -> web.Response:
        return web.Response(text=DASHBOARD_HTML, content_type="text/html")

    async def handle_favicon(self, _request: web.Request) -> web.Response:
        return web.Response(status=204)

    async def handle_overview(self, request: web.Request) -> web.Response:
        records, start_dt, end_dt, model, query, _, page, page_size = self._load_filtered_records(
            request, limit_cap=1000
        )
        payload = build_overview_payload(
            records=records,
            start_dt=start_dt,
            end_dt=end_dt,
            model=model,
            query=query,
            page=page,
            page_size=page_size,
            available_models=self.store.list_models(),
            proxy_label=self.proxy_label,
            upstream_label=self.upstream_label,
        )
        return web.json_response(payload)

    async def handle_export_csv(self, request: web.Request) -> web.Response:
        records, _, _, _, _, limit, _, _ = self._load_filtered_records(request, limit_cap=5000)
        csv_text = _records_to_csv(list(reversed(records[-limit:])))
        response = web.Response(text=csv_text, content_type="text/csv")
        response.headers["Content-Disposition"] = 'attachment; filename="ollama-monitor-export.csv"'
        return response
