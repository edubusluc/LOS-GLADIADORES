function initializeCharts(data) {
    const { totalWins, totalLost, presentCall, noCall, years, gamesWonPerYear, gamesLostPerYear } = data;

    const pieChart = document.getElementById('myPieChart');
    const chartCall = document.getElementById('chartCall');
    const localWinLost = document.getElementById('localWinLost');
    const visitingWinLost = document.getElementById('visitingWinLost');
    const lineGamesChart = document.getElementById('myLineGamesChart');

    if (pieChart) {
        const pieCtx = pieChart.getContext('2d');
        new Chart(pieCtx, {
            type: 'pie',
            data: {
                labels: ['Ganados', 'Perdidos'],
                datasets: [{
                    data: [totalWins, totalLost],
                    backgroundColor: ['#083C64', '#ff6384'],
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    if (chartCall) {
        const pieCallCtx = chartCall.getContext('2d');
        new Chart(pieCallCtx, {
            type: 'pie',
            data: {
                labels: ['Llamado', 'No llamado'],
                datasets: [{
                    data: [presentCall, noCall],
                    backgroundColor: ['#083C64', '#ff6384'],
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    if (localWinLost) {
        const localWinLostCtx = localWinLost.getContext('2d');
        new Chart(localWinLostCtx, {
            type: 'bar',
            data: {
                labels: ['Partidos Ganados', 'Partidos Perdidos'],
                datasets: [{
                    data: [data.won_games_local, data.lost_games_local],
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
    }

    if (visitingWinLost) {
        const visitingWinLostCtx = visitingWinLost.getContext('2d');
        new Chart(visitingWinLostCtx, {
            type: 'bar',
            data: {
                labels: ['Partidos Ganados', 'Partidos Perdidos'],
                datasets: [{
                    data: [data.won_games_visiting, data.lost_games_visiting],
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
    }

    if (lineGamesChart) {
        const lineGamesCtx = lineGamesChart.getContext('2d');
        new Chart(lineGamesCtx, {
            type: 'line',
            data: {
                labels: years,
                datasets: [
                    {
                        label: 'Partidos Ganados',
                        data: gamesWonPerYear,
                        fill: true,
                        backgroundColor: 'rgba(8, 60, 100, 0.2)',
                        borderColor: '#083C64',
                        tension: 0.1
                    },
                    {
                        label: 'Partidos Perdidos',
                        data: gamesLostPerYear,
                        fill: true, 
                        backgroundColor: 'rgba(255, 99, 132, 0.2)', 
                        borderColor: '#ff6384', 
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true // Puedes cambiar esto a false si no quieres mostrar la leyenda
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
    }
    
}
