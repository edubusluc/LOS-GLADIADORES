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
const years = Object.keys(teamData.matchesWonPerYear);
    const wonMatches = years.map(year => teamData.matchesWonPerYear[year].won);
    const lostMatches = years.map(year => teamData.matchesWonPerYear[year].lost);

    // Configuración del gráfico
    const ctx = document.getElementById('myLineChart').getContext('2d');
    const myLineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: years,
            datasets: [
                {
                    label: 'Partidos Ganados',
                    data: wonMatches,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    fill: true
                },
                {
                    label: 'Partidos Perdidos',
                    data: lostMatches,
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    fill: true
                }
            ]
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

// Gráfico de columnas para partidos ganados/perdidos
const columnCtx = document.getElementById('myColumnChart').getContext('2d');
// Procesar los datos para el gráfico de columnas
const labels = teamData.column_chart_data.map(entry => entry.player);
const partidos2Ganados = teamData.column_chart_data.map(entry => entry.data[0]); // Partidos de 2 puntos ganados
const partidos2Perdidos = teamData.column_chart_data.map(entry => entry.data[1]); // Partidos de 2 puntos perdidos
const partidos3Ganados = teamData.column_chart_data.map(entry => entry.data[2]); // Partidos de 3 puntos ganados
const partidos3Perdidos = teamData.column_chart_data.map(entry => entry.data[3]); // Partidos de 3 puntos perdidos

const myColumnChart = new Chart(columnCtx, {
  type: 'bar',
  data: {
      labels: labels,
      datasets: [
          {
              label: 'Partidos de 2 puntos ganados',
              data: partidos2Ganados,
              backgroundColor: '#007BFF', // Azul brillante
          },
          {
              label: 'Partidos de 2 puntos perdidos',
              data: partidos2Perdidos,
              backgroundColor: '#FFA500', 
          },
          {
              label: 'Partidos de 3 puntos ganados',
              data: partidos3Ganados,
              backgroundColor: '#0056b3', // Azul oscuro
          },
          {
              label: 'Partidos de 3 puntos perdidos',
              data: partidos3Perdidos,
              backgroundColor: 'rgba(255, 215, 0, 0.8)', // Amarillo dorado
          }
      ]
  },
  options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
          legend: {
              display: true
          }
      },
      scales: {
          y: {
              beginAtZero: true,
              stacked: true,
              title: {
                  display: true,
                  text: 'Número de Partidos',
                  font: {
                      size: 16,
                  },
                  padding: {
                      top: 10,
                      bottom: 10
                  }
              }
          },
          x: {
              stacked: true
          }
      }
  }
});
