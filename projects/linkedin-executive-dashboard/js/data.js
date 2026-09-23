window.DASHBOARD_DATA = {
  months: ["Apr", "May", "Jun", "Jul", "Aug", "Sep"],
  trend: {
    recognized: [3.82, 4.05, 4.21, 4.48, 4.62, 4.91],
    bookings: [4.55, 4.72, 4.88, 4.95, 5.02, 5.18],
  },
  regions: [
    { name: "West", revenue: 1.72, region: "West" },
    { name: "East", revenue: 1.35, region: "East" },
    { name: "Central", revenue: 1.08, region: "Central" },
    { name: "South", revenue: 0.76, region: "South" },
  ],
  aging: [
    { bucket: "Current", amount: 1.42 },
    { bucket: "1–30", amount: 0.68 },
    { bucket: "31–60", amount: 0.31 },
    { bucket: "61–90", amount: 0.18 },
    { bucket: "90+", amount: 0.11 },
  ],
  accounts: [
    { name: "Northwind Logistics", region: "West", bu: "Wholesale", revenue: 820000, margin: 0.34, ar: 92000 },
    { name: "Cascade Retail Co", region: "West", bu: "Retail", revenue: 640000, margin: 0.29, ar: 74000 },
    { name: "Harbor Ecom Group", region: "East", bu: "Ecom", revenue: 590000, margin: 0.41, ar: 38000 },
    { name: "Prairie Wholesale", region: "Central", bu: "Wholesale", revenue: 470000, margin: 0.27, ar: 115000 },
    { name: "Sunbelt Stores", region: "South", bu: "Retail", revenue: 410000, margin: 0.31, ar: 56000 },
    { name: "Metro Direct", region: "East", bu: "Ecom", revenue: 385000, margin: 0.38, ar: 29000 },
    { name: "Great Lakes Dist.", region: "Central", bu: "Wholesale", revenue: 360000, margin: 0.25, ar: 88000 },
    { name: "Pacific Outfitters", region: "West", bu: "Retail", revenue: 320000, margin: 0.33, ar: 41000 },
  ],
  kpis: {
    all: {
      revenue: 4910000,
      revenueDelta: 0.063,
      margin: 0.328,
      marginDelta: 0.014,
      variance: 270000,
      varianceDelta: -0.72,
      otd: 0.942,
      otdDelta: 0.028,
    },
  },
};
