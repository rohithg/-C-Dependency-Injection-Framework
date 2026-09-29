
(() => {
  const programs = { "Energy Efficiency": 4.2e6, "Demand Response": 2.1e6, "Solar Rebate": 1.6e6, "EV Charger Incentive": 0.9e6 };
  const utilities = [
    { name: "Pacific Gas Utility", rate: 0.96 },
    { name: "Desert Sun Electric", rate: 0.91 },
    { name: "Rocky Mountain Power", rate: 0.88 },
    { name: "Great Lakes Energy", rate: 0.94 },
    { name: "Atlantic Coast Power", rate: 0.87 },
  ];
  const totalKwh = Object.values(programs).reduce((a,b)=>a+b,0);
  document.getElementById("kpiKwh").textContent = (totalKwh/1e6).toFixed(2) + "M";
  document.getElementById("kpiSpend").textContent = "$1.84M";
  document.getElementById("kpiComp").textContent = "91.2%";
  document.getElementById("kpiPeak").textContent = "18.4 MW";
  const boot = () => {
    if (typeof Chart === "undefined") return setTimeout(boot, 40);
    new Chart(document.getElementById("progChart"), {
      type: "bar",
      data: { labels: Object.keys(programs), datasets: [{ label: "kWh", data: Object.values(programs), backgroundColor: "#1f7a4d" }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => (v/1e6).toFixed(1)+"M" } } } }
    });
    new Chart(document.getElementById("utilChart"), {
      type: "doughnut",
      data: { labels: utilities.map(u=>u.name), datasets: [{ data: utilities.map(u=>u.rate*100), backgroundColor: ["#0b1f17","#1f7a4d","#3aa06a","#7bc49a","#c8e6d4"] }] },
      options: { plugins: { tooltip: { callbacks: { label: c => c.label + ": " + c.parsed.toFixed(1) + "%" } } } }
    });
  };
  boot();
})();
