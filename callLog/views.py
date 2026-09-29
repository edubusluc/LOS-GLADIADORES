from django.shortcuts import render
from callLog.models import CallLog
from players.models import Player
from django.views.decorators.http import require_http_methods
from core.decorators import club_required

# Create your views here.
@club_required
@require_http_methods(["GET", "POST"])
def view_call_log(request, call_id):
    # Solo los jugadores que siguen en el equipo, por orden alfabético
    players = Player.objects.filter(club=request.club, in_team=True).order_by('name', 'last_name')
    try:
        call_log = CallLog.objects.get(call=call_id, call__match__club=request.club)
    except CallLog.DoesNotExist:
        return render(request, "view_call_log.html", {
            "error_message": "No se encontró el registro de llamada con el ID especificado.",
            "log_lines": [],
            "players": players,
            "call_id": call_id,
        })

    if call_log.text:
        log_lines = call_log.text.split(";")
    else:
        log_lines = []  # Si no tiene contenido, usar una lista vacía

    return render(request, "view_call_log.html", {
        "log_lines": log_lines,
        "players": players,
        "call_id":call_id
    })
