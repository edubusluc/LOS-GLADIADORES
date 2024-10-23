from django.shortcuts import redirect
from players.models import Player
from .models import Penalty
from call.models import Call

# Create your views here.
def create_penalty(request, call_id):
    call = Call.objects.get(id=call_id)
    match = call.match
    if request.method == "POST":
        selected_players_ids = request.POST.getlist('players')
        for selected in selected_players_ids:
            player = Player.objects.get(id = selected)

            penalty = Penalty.objects.create(
                player = player,
                reason = "Advertencia en el partido " + match.local.name + " VS " + match.visiting.name + ".",
                call = call
            )
            penalty.save()
        
        return redirect("call_for_match", match.id)
    return redirect("call_for_match", match.id)




