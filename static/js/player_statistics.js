(function () {
  const read = (id) => JSON.parse(document.getElementById(id).textContent);
  const seasons = read('data-seasons');
  const affinity = read('data-affinity');

  const C = {
    navy: '#083C64',
    gold: '#E0AE55',
    win: '#1F8A70',
    loss: '#C8434F',
    muted: '#5F7286',
    line: '#DCE3EA',
  };

  Chart.defaults.font.family = "'Barlow', system-ui, sans-serif";
  Chart.defaults.color = C.muted;

  const base = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } } },
  };

  // Partidos jugados por temporada (ganados + perdidos apilados)
  new Chart(document.getElementById('chartPlayed'), {
    type: 'bar',
    data: {
      labels: seasons.labels,
      datasets: [
        { label: 'Ganados', data: seasons.wins, backgroundColor: C.win, borderRadius: 4 },
        { label: 'Perdidos', data: seasons.losses, backgroundColor: C.loss, borderRadius: 4 },
      ],
    },
    options: {
      ...base,
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, grid: { color: C.line } },
      },
    },
  });

  // Evolución del % de victorias
  new Chart(document.getElementById('chartPct'), {
    type: 'line',
    data: {
      labels: seasons.labels,
      datasets: [{
        label: '% victorias',
        data: seasons.pct,
        borderColor: C.navy,
        backgroundColor: 'rgba(8, 60, 100, 0.08)',
        pointBackgroundColor: C.gold,
        pointBorderColor: C.navy,
        pointRadius: 5,
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      ...base,
      plugins: { ...base.plugins, legend: { display: false },
        tooltip: { callbacks: { label: (c) => ` ${c.parsed.y}%` } } },
      scales: {
        x: { grid: { display: false } },
        y: { min: 0, max: 100, ticks: { callback: (v) => v + '%' }, grid: { color: C.line } },
      },
    },
  });

  // Afinidad con compañeros (barras horizontales)
  const entries = Object.entries(affinity).filter(([, v]) => v > 0);
    new Chart(document.getElementById('chartAffinity'), {
    type: 'bar',
    data: {
      labels: affinity.map((a) => `${a.name} (${a.games})`),
      datasets: [{
        label: 'Afinidad',
        data: affinity.map((a) => a.affinity),
        // por encima del 50 % rinden mejor de lo esperado juntos
        backgroundColor: affinity.map((a) => (a.affinity >= 50 ? C.win : C.loss)),
        borderRadius: 4,
      }],
    },
    options: {
      ...base,
      indexAxis: 'y',
      plugins: {
        ...base.plugins,
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (c) => {
              const a = affinity[c.dataIndex];
              return ` ${a.affinity}% · ${a.wins}V - ${a.losses}D`;
            },
          },
        },
      },
      scales: {
        x: { min: 0, max: 100, grid: { color: C.line } },
        y: { grid: { display: false } },
      },
    },
  });
})();