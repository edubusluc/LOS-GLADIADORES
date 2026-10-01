(function () {
  const read = (id) => JSON.parse(document.getElementById(id).textContent);
  const seasons = read('data-seasons');
  const affinity = read('data-affinity');

  // Paleta Zyra (tema oscuro)
  const C = {
    navy: '#B4F100',
    gold: '#B4F100',
    win: '#B4F100',
    loss: '#FF5C63',
    muted: '#A3A3A3',
    line: 'rgba(255, 255, 255, 0.08)',
  };

  Chart.defaults.font.family = "'Archivo', system-ui, sans-serif";
  Chart.defaults.color = C.muted;
  Chart.defaults.borderColor = C.line;

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
        backgroundColor: 'rgba(180, 241, 0, 0.15)',
        pointBackgroundColor: C.gold,
        pointBorderColor: '#0B0B0B',
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

  // Evolución de los puntos SNP en la temporada (mismo estilo que el % de victorias)
  const snp = read('data-snp');
  const snpCanvas = document.getElementById('chartSnp');
  if (snpCanvas) {
    new Chart(snpCanvas, {
      type: 'line',
      data: {
        labels: snp.labels,
        datasets: [{
          label: 'Puntos SNP',
          data: snp.scores,
          borderColor: C.navy,
          backgroundColor: 'rgba(180, 241, 0, 0.15)',
          pointBackgroundColor: C.gold,
          pointBorderColor: '#0B0B0B',
          pointRadius: 5,
          tension: 0.3,
          fill: true,
        }],
      },
      options: {
        ...base,
        plugins: { ...base.plugins, legend: { display: false },
          tooltip: { callbacks: { label: (c) => ` ${c.parsed.y.toLocaleString('es-ES')} puntos` } } },
        scales: {
          x: { grid: { display: false } },
          y: { ticks: { callback: (v) => v.toLocaleString('es-ES') }, grid: { color: C.line } },
        },
      },
    });
  }

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