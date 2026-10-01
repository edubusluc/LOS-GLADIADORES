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

// Balance por jugador: partidos de 2 y 3 puntos, ganados y perdidos
const rows = teamData.column_chart_data;
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
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' } },
    scales: scales({ x: { stacked: true }, y: { stacked: true, title: { display: true, text: gettext('Partidos') } } }),
  },
});
