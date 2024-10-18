from django.shortcuts import render
from callLog.models import CallLog
from players.models import Player

# Create your views here.

def view_call_log(request, call_id):
    callLog = CallLog.objects.get(call=call_id)

    players = Player.objects.all()

    log_lines = callLog.text.split(";")

    for l in log_lines:
        print(l)

    return render(request,"view_call_log.html", {"log_lines":log_lines, "players":players})