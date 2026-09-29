
(() => {
  const carriers = [
    { name: "FXFE", otif: 0.86 }, { name: "ODFL", otif: 0.91 },
    { name: "XPO", otif: 0.84 }, { name: "JBHT", otif: 0.88 },
    { name: "UPGF", otif: 0.90 }, { name: "AMZL", otif: 0.93 },
  ];
  document.getElementById("kOtif").textContent = "87.4%";
  document.getElementById("kOn").textContent = "91.1%";
  document.getElementById("kFull").textContent = "94.0%";
  document.getElementById("kYard").textContent = "11.2h";
  const boot = () => {
    if (typeof Chart === "undefined") return setTimeout(boot, 40);
    new Chart(document.getElementById("carrierChart"), {
      type: "bar",
      data: { labels: carriers.map(c => c.name),
        datasets: [{ label: "OTIF", data: carriers.map(c => c.otif * 100), backgroundColor: "#1a9e9e" }] },
      options: { scales: { y: { min: 70, max: 100, ticks: { callback: v => v + "%" } } },
                 plugins: { legend: { display: false } } },
    });
  };
  boot();
})();
