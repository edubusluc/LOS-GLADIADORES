// Paleta Zyra: lima para victorias, coral para derrotas, sobre fondo oscuro.
const Z = {
  lime: '#B4F100',
  limeDark: '#6E9400',
  coral: '#FF5C63',
  coralDark: '#9E3A3F',
  text: '#A3A3A3',
  grid: 'rgba(255, 255, 255, 0.08)',
  card: '#151515',
};

Chart.defaults.font.family = "'Archivo', system-ui, sans-serif";
Chart.defaults.color = Z.text;
Chart.defaults.borderColor = Z.grid;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.boxWidth = 8;

const scales = (extra = {}) => ({
  x: { grid: { display: false }, ...extra.x },
  y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: Z.grid }, ...extra.y },
});

// Partidos ganados / perdidos
new Chart(document.getElementById('myPieChart'), {
  type: 'doughnut',
  data: {
    labels: [gettext('Ganados'), gettext('Perdidos')],
    datasets: [{
      data: [teamData.wonMatches, teamData.lostMatches],
      backgroundColor: [Z.lime, Z.coral],
      borderColor: Z.card,
      borderWidth: 4,
    }],
  },
  options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom' } } },
});

// Juegos ganados / perdidos como local y como visitante
const gamesBar = (id, won, lost) => new Chart(document.getElementById(id), {
  type: 'bar',
  data: {
    labels: [gettext('Ganados'), gettext('Perdidos')],
    datasets: [{ data: [won, lost], backgroundColor: [Z.lime, Z.coral], borderRadius: 8, maxBarThickness: 64 }],
  },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: scales() },
});
gamesBar('myBarChart', teamData.localGamesWon, teamData.localGamesLost);
gamesBar('myVisitingBarChart', teamData.visitingGamesWon, teamData.visitingGamesLost);

// Partidos ganados y perdidos por temporada
const years = Object.keys(teamData.matchesWonPerYear);
new Chart(document.getElementById('myLineChart'), {
  type: 'line',
  data: {
    labels: years,
    datasets: [
      {
        label: gettext('Ganados'),
        data: years.map((y) => teamData.matchesWonPerYear[y].won),
        borderColor: Z.lime,
        backgroundColor: 'rgba(180, 241, 0, 0.18)',
        pointBackgroundColor: Z.lime,
        tension: 0.35,
        fill: true,
      },
      {
        label: gettext('Perdidos'),
        data: years.map((y) => teamData.matchesWonPerYear[y].lost),
        borderColor: Z.coral,
        backgroundColor: 'rgba(255, 92, 99, 0.10)',
        pointBackgroundColor: Z.coral,
        tension: 0.35,
        fill: true,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' } },
    scales: scales({ y: { title: { display: true, text: gettext('Partidos') } } }),
  },
});

// Balance por jugador: partidos de 2 y 3 puntos, ganados y perdidos.
// Barras horizontales: un jugador por fila, así los nombres se leen enteros y
// el gráfico crece hacia abajo cuando el equipo tiene muchos jugadores.
const total = (r) => r.data.reduce((a, b) => a + b, 0);
const rows = [...teamData.column_chart_data].sort((a, b) => total(b) - total(a));
const balanceBox = document.getElementById('balanceChart');
const ROW_HEIGHT = 30;
balanceBox.style.height = `${Math.max(rows.length, 3) * ROW_HEIGHT + 110}px`;

const PARTICLES = new Set(['de', 'del', 'la', 'las', 'los', 'y', 'da', 'do', 'dos', 'van', 'von']);
// En pantallas estrechas: "Eduardo Bustamante Lucena" -> "E. Bustamante"
const shortName = (name, max) => {
  if (name.length <= max) return name;
  const parts = name.trim().split(/\s+/);
  // Salta partículas para que "Marcos de la Fuente" quede "M. Fuente"
  const surname = parts.slice(1).find((w) => !PARTICLES.has(w.toLowerCase()));
  const short = surname ? `${parts[0][0]}. ${surname}` : name;
  return short.length <= max ? short : `${short.slice(0, max - 1)}…`;
};
const labelMax = () => (balanceBox.clientWidth < 520 ? 14 : 26);

new Chart(document.getElementById('myColumnChart'), {
  type: 'bar',
  data: {
    labels: rows.map((r) => r.player),
    datasets: [
      { label: gettext('2 puntos ganados'), data: rows.map((r) => r.data[0]), backgroundColor: Z.lime },
      { label: gettext('3 puntos ganados'), data: rows.map((r) => r.data[2]), backgroundColor: Z.limeDark },
      { label: gettext('2 puntos perdidos'), data: rows.map((r) => r.data[1]), backgroundColor: Z.coral },
      { label: gettext('3 puntos perdidos'), data: rows.map((r) => r.data[3]), backgroundColor: Z.coralDark },
    ],
  },
  options: {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    datasets: { bar: { barPercentage: 0.8, categoryPercentage: 0.9, maxBarThickness: 22 } },
    interaction: { mode: 'index', axis: 'y', intersect: false },
    plugins: {
      legend: { position: 'top' },
      tooltip: {
        callbacks: {
          footer: (items) => `${gettext('Partidos')}: ${items.reduce((a, i) => a + i.parsed.x, 0)}`,
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        beginAtZero: true,
        position: 'top',
        ticks: { precision: 0 },
        grid: { color: Z.grid },
        title: { display: true, text: gettext('Partidos') },
      },
      y: {
        stacked: true,
        grid: { display: false },
        ticks: {
          autoSkip: false,
          callback(value) { return shortName(this.getLabelForValue(value), labelMax()); },
        },
      },
    },
  },
});
