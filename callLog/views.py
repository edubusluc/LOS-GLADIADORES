from django.shortcuts import render
from callLog.models import CallLog
from players.models import Player
from django.views.decorators.http import require_http_methods

# Create your views here.
@require_http_methods(["GET", "POST"])
def view_call_log(request, call_id):
    try:
        call_log = CallLog.objects.get(call=call_id)
    except CallLog.DoesNotExist:
        return render(request, "view_call_log.html", {
            "error_message": "No se encontró el registro de llamada con el ID especificado.",
            "log_lines": [],
            "players": Player.objects.all()
        })

    players = Player.objects.all()
    log_lines = call_log.text.split(";")

    for l in log_lines:
        print(l)

    return render(request, "view_call_log.html", {
        "log_lines": log_lines,
        "players": players,
        "call_id":call_id
    })