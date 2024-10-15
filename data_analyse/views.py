from django.shortcuts import render
from match.models import *  
from team.models import *
from datetime import date
from datetime import datetime

def team_statistics(request):
    actual_year = request.GET.get('year', datetime.now().year)
    all_matchs = Match.objects.all()

    selected_year = request.GET.get('year', None)
    
    # Establecer un valor por defecto (por ejemplo, el año actual)
    if selected_year:
        try:
            actual_year = int(selected_year)
        except ValueError:
            actual_year = datetime.now().year  # O cualquier otro valor predeterminado
    else:
        actual_year = datetime.now().year

    for m in all_matchs:
        years = {m.start_date.year}
    
    team = Team.objects.filter(name = "LOS GLADIADORES")
    if team:
        team = team.first()
    else:
        return render('team_statistics.html')
    

    # Cálculo de partidos ganados/perdidos
    total_matches = Match.objects.filter(start_date__year = actual_year, draft_mode= False).count()
    won_local = Match.objects.filter(start_date__year = actual_year, local=team, result="Victoria Local", draft_mode = False).count()
    won_visiting = Match.objects.filter(start_date__year = actual_year, visiting=team, result="Victoria Visitante",draft_mode = False).count()

    total_won = won_local + won_visiting
    lost_matches = total_matches - total_won
 
    percentage_won = round((total_won/total_matches)*100,2) if total_matches > 0 else 0
    percentage_lost = round((lost_matches/total_matches)*100,2) if total_matches > 0 else 0

    # Cálculo de juegos ganados/perdidos como LOCAL
    match_local = Match.objects.filter(start_date__year = actual_year, local=team, draft_mode = False)

    local_games_won = 0
    local_games_lost = 0

    for m in match_local:
        games = m.games.all()
        for g in games:
            result = g.results.first()  # Obtiene el resultado asociado al juego
            # Suma los sets ganados y perdidos por el equipo local
            local_games_won += result.set1_local + result.set2_local + (result.set3_local or 0)
            local_games_lost += result.set1_visiting + result.set2_visiting + (result.set3_visiting or 0)

    total_local_games = local_games_lost + local_games_won

    percentage_local_games_won = round((local_games_won / total_local_games * 100), 2) if total_local_games > 0 else 0
    percentage_local_games_lost = round((local_games_lost/total_local_games)*100,2) if total_local_games > 0 else 0

  
    # Cálculo de juegos ganados/perdidos como VISITANTE
    match_visiting = Match.objects.filter(start_date__year = actual_year, visiting=team, draft_mode = False)

    visiting_games_won = 0
    visiting_games_lost = 0

    for m in match_visiting:
        games = m.games.all()
        for g in games:
            result = g.results.first()  # Obtiene el resultado asociado al juego
            # Suma los sets ganados y perdidos por el equipo local
            visiting_games_won += result.set1_visiting + result.set2_visiting + (result.set3_visiting or 0)
            visiting_games_lost += result.set1_local + result.set2_local + (result.set3_local or 0)

    total_visiting_games = visiting_games_won + visiting_games_lost
    percentage_visiting_games_won = round((visiting_games_won/total_visiting_games)*100,2) if total_visiting_games > 0 else 0
    percentage_visiting_games_lost = round((visiting_games_lost/total_visiting_games)*100,2) if total_visiting_games > 0 else 0



    #Gráfico de linea partidos ganados por año
    dicc_match = {}
    for m in all_matchs:
        years = {m.start_date.year}
        
        for y in years:
            if y not in dicc_match.keys():
                dicc_match[y] = {
                    'won':0
            }
            #total_match = Match.objects.filter(start_date__year=y = y, draft_mode = False).count()
            match_wonLocal = Match.objects.filter(start_date__year = y, local = team, result = "Victoria Local", draft_mode = False).count()
            match_wonVisiting = Match.objects.filter(start_date__year = y, visiting = team, result = "Victoria Visitante", draft_mode = False).count()
            won = match_wonLocal + match_wonVisiting
            dicc_match[y]['won'] = won    
    
    
    years = sorted(dicc_match.keys())
    matches_won_per_year = [dicc_match[y]['won'] for y in years]  
                
    # Contexto para la plantilla
    context = {
        'team':team,
        'actual_year':actual_year,
        'total_matches': total_matches,
        'won_matches': total_won,
        'lost_matches': lost_matches,
        'local_games_won': local_games_won,
        'local_games_lost': local_games_lost,
        'percentage_won': percentage_won,
        'percentage_lost': percentage_lost,
        'visiting_games_won': visiting_games_won,
        'visiting_games_lost': visiting_games_lost,
        'percentage_local_games_won': percentage_local_games_won,
        'percentage_local_games_lost': percentage_local_games_lost,
        'percentage_visiting_games_won': percentage_visiting_games_won,
        'percentage_visiting_games_lost': percentage_visiting_games_lost,
        'years': years,
        'matches_won_per_year': matches_won_per_year,

    }

    return render(request, 'team_statistics.html', context)
