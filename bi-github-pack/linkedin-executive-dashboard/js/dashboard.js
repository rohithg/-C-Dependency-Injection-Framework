(() => {
  const money = (n) => {
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${n.toFixed(0)}`;
  };
  const pct = (n, digits = 1) => `${(n * 100).toFixed(digits)}%`;
  const signedPct = (n) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)}% vs prior`;

  const state = { region: "all", bu: "all", account: null };
  let trendChart, regionChart, agingChart;

  const filteredAccounts = () =>
    window.DASHBOARD_DATA.accounts.filter((a) => {
      if (state.region !== "all" && a.region !== state.region) return false;
      if (state.bu !== "all" && a.bu !== state.bu) return false;
      return true;
    });

  const scale = () => {
    const rows = filteredAccounts();
    const all = window.DASHBOARD_DATA.accounts;
    const sum = (arr, key) => arr.reduce((s, r) => s + r[key], 0);
    const ratio = all.length ? sum(rows, "revenue") / sum(all, "revenue") : 1;
    return Math.max(0.35, Math.min(1, ratio || 1));
  };

  const renderKpis = () => {
    const base = window.DASHBOARD_DATA.kpis.all;
    const s = scale();
    document.getElementById("kpiRevenue").textContent = money(base.revenue * s);
    document.getElementById("kpiRevenueDelta").textContent = signedPct(base.revenueDelta);
    document.getElementById("kpiMargin").textContent = pct(base.margin);
    document.getElementById("kpiMarginDelta").textContent = signedPct(base.marginDelta);
    document.getElementById("kpiVariance").textContent = money(base.variance * s);
    document.getElementById("kpiVarianceDelta").textContent = `${signedPct(base.varianceDelta)} (gap closed)`;
    document.getElementById("kpiOtd").textContent = pct(base.otd);
    document.getElementById("kpiOtdDelta").textContent = signedPct(base.otdDelta);
  };

  const renderTable = () => {
    const tbody = document.getElementById("accountTable");
    const rows = filteredAccounts().sort((a, b) => b.revenue - a.revenue);
    tbody.innerHTML = rows
      .map(
        (a) => `
      <tr data-account="${a.name}" class="${state.account === a.name ? "is-active" : ""}">
        <td>${a.name}</td>
        <td>${a.region}</td>
        <td>${a.bu}</td>
        <td class="num">${money(a.revenue)}</td>
        <td class="num">${pct(a.margin, 0)}</td>
        <td class="num">${money(a.ar)}</td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", () => {
        state.account = tr.dataset.account;
        renderTable();
        updateTrendHighlight();
      });
    });
  };

  const chartDefaults = () => {
    Chart.defaults.font.family = "'Sora', system-ui, sans-serif";
    Chart.defaults.color = "#5a6d82";
    Chart.defaults.borderColor = "rgba(10,22,40,0.08)";
  };

  const buildCharts = () => {
    chartDefaults();
    const { months, trend, regions, aging } = window.DASHBOARD_DATA;
    const s = scale();

    trendChart = new Chart(document.getElementById("trendChart"), {
      type: "line",
      data: {
        labels: months,
        datasets: [
          {
            label: "Recognized net revenue",
            data: trend.recognized.map((v) => +(v * s).toFixed(2)),
            borderColor: "#1a9e9e",
            backgroundColor: "rgba(62,207,207,0.15)",
            fill: true,
            tension: 0.35,
            pointRadius: 4,
            pointBackgroundColor: "#1a9e9e",
          },
          {
            label: "Closed-won bookings",
            data: trend.bookings.map((v) => +(v * s).toFixed(2)),
            borderColor: "#e8a317",
            backgroundColor: "transparent",
            borderDash: [5, 4],
            tension: 0.35,
            pointRadius: 3,
            pointBackgroundColor: "#e8a317",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: $${ctx.parsed.y.toFixed(2)}M`,
            },
          },
        },
        scales: {
          y: {
            ticks: { callback: (v) => `$${Number(v).toFixed(1)}M` },
            grid: { color: "rgba(10,22,40,0.06)" },
          },
          x: { grid: { display: false } },
        },
      },
    });

    regionChart = new Chart(document.getElementById("regionChart"), {
      type: "doughnut",
      data: {
        labels: regions.map((r) => r.name),
        datasets: [
          {
            data: regions.map((r) => {
              if (state.region !== "all" && r.region !== state.region) return 0.01;
              return r.revenue * s;
            }),
            backgroundColor: ["#0d3d3a", "#1a9e9e", "#3ecfcf", "#e8a317"],
            borderWidth: 0,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        cutout: "62%",
        plugins: {
          legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.label}: $${ctx.parsed.toFixed(2)}M`,
            },
          },
        },
      },
    });

    agingChart = new Chart(document.getElementById("agingChart"), {
      type: "bar",
      data: {
        labels: aging.map((a) => a.bucket),
        datasets: [
          {
            label: "AR ($M)",
            data: aging.map((a) => +(a.amount * s).toFixed(2)),
            backgroundColor: ["#1a9e9e", "#3ecfcf", "#e8a317", "#e08a3d", "#d64545"],
            borderRadius: 4,
            barPercentage: 0.7,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          y: {
            ticks: { callback: (v) => `$${Number(v).toFixed(1)}M` },
            grid: { color: "rgba(10,22,40,0.06)" },
          },
          x: { grid: { display: false } },
        },
      },
    });
  };

  const refreshCharts = () => {
    const s = scale();
    const { trend, regions, aging } = window.DASHBOARD_DATA;

    trendChart.data.datasets[0].data = trend.recognized.map((v) => +(v * s).toFixed(2));
    trendChart.data.datasets[1].data = trend.bookings.map((v) => +(v * s).toFixed(2));
    trendChart.update();

    regionChart.data.datasets[0].data = regions.map((r) => {
      if (state.region !== "all" && r.region !== state.region) return 0.01;
      return +(r.revenue * s).toFixed(2);
    });
    regionChart.update();

    agingChart.data.datasets[0].data = aging.map((a) => +(a.amount * s).toFixed(2));
    agingChart.update();
  };

  const updateTrendHighlight = () => {
    // Soft visual cue only — keeps charts stable for LinkedIn screenshots
    document.querySelectorAll(".panel-wide")[0]?.classList.toggle("is-focused", !!state.account);
  };

  const refresh = () => {
    renderKpis();
    renderTable();
    refreshCharts();
  };

  const boot = () => {
    if (typeof Chart === "undefined") {
      setTimeout(boot, 40);
      return;
    }
    buildCharts();
    renderKpis();
    renderTable();

    document.getElementById("regionFilter").addEventListener("change", (e) => {
      state.region = e.target.value;
      state.account = null;
      refresh();
    });
    document.getElementById("buFilter").addEventListener("change", (e) => {
      state.bu = e.target.value;
      state.account = null;
      refresh();
    });
  };

  boot();
})();
