
(() => {
  const k = window.OTIF_KPIS;
  const carriers = window.OTIF_DATA;
  const pct = (x) => (x * 100).toFixed(1) + "%";
  document.getElementById("kOtif").textContent = pct(k.otif);
  document.getElementById("kOn").textContent = pct(k.on_time);
  document.getElementById("kFull").textContent = pct(k.in_full);
  document.getElementById("kYard").textContent = k.avg_dwell.toFixed(1) + "h";
  const boot = () => {
    if (typeof Chart === "undefined") return setTimeout(boot, 40);
    new Chart(document.getElementById("carrierChart"), {
      type: "bar",
      data: {
        labels: carriers.map((c) => c.name),
        datasets: [{ label: "OTIF", data: carriers.map((c) => c.otif * 100), backgroundColor: "#1a9e9e" }],
      },
      options: {
        scales: { y: { min: 50, max: 100, ticks: { callback: (v) => v + "%" } } },
        plugins: { legend: { display: false },
          tooltip: { callbacks: { afterLabel: (ctx) => {
            const c = carriers[ctx.dataIndex];
            return `n=${c.shipments}  on-time=${(c.on_time*100).toFixed(1)}%  in-full=${(c.in_full*100).toFixed(1)}%`;
          } } } },
      },
    });
  };
  boot();
})();
