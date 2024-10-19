// charts.js

// Gráfico de pastel para partidos ganados/perdidos
const pieCtx = document.getElementById('myPieChart').getContext('2d');
const myPieChart = new Chart(pieCtx, {
  type: 'pie',
  data: {
    labels: ['Ganados', 'Perdidos'],
    datasets: [{
      data: [teamData.wonMatches, teamData.lostMatches],
      backgroundColor: ['#083C64', '#ff6384'],
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false
  }
});

// Gráfico de barras para juegos ganados/perdidos como Local
const barCtx = document.getElementById('myBarChart').getContext('2d');
const myBarChart = new Chart(barCtx, {
  type: 'bar',
  data: {
    labels: ['Juegos Ganados', 'Juegos Perdidos'],
    datasets: [{
      data: [teamData.localGamesWon, teamData.localGamesLost],
      backgroundColor: ['#083C64', '#ff6384'],
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      }
    },
    scales: {
      y: {
        beginAtZero: true
      }
    }
  }
});

// Gráfico de barras para juegos ganados/perdidos como Visitante
const visitingBarCtx = document.getElementById('myVisitingBarChart').getContext('2d');
const myVisitingBarChart = new Chart(visitingBarCtx, {
  type: 'bar',
  data: {
    labels: ['Juegos Ganados', 'Juegos Perdidos'],
    datasets: [{
      data: [teamData.visitingGamesWon, teamData.visitingGamesLost],
      backgroundColor: ['#083C64', '#ff6384'],
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      }
    },
    scales: {
      y: {
        beginAtZero: true
      }
    }
  }
});

// Gráfico de línea para el número de partidos ganados por año
const lineCtx = document.getElementById('myLineChart').getContext('2d');
const myLineChart = new Chart(lineCtx, {
  type: 'line',
  data: {
    labels: teamData.years,  // Usar teamData
    datasets: [{
      label: 'Partidos Ganados',
      data: teamData.matchesWonPerYear,  // Usar teamData
      backgroundColor: 'rgba(8, 60, 100, 0.2)',
      borderColor: '#083C64',
      borderWidth: 2,
      fill: true,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Año'
        }
      },
      y: {
        title: {
          display: true,
          text: 'Número de Partidos Ganados'
        },
        beginAtZero: true
      }
    }
  }
});
