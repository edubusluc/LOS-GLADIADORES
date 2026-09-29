from django.shortcuts import redirect, get_object_or_404
from .models import Penalty
from call.models import Call
from core.decorators import club_admin_required

@club_admin_required
def create_penalty(request, call_id):
    call = get_object_or_404(Call, id=call_id, match__club=request.club)
    match = call.match
    if request.method == "POST":
        selected_players_ids = request.POST.getlist('players')
        # Solo se puede sancionar a jugadores de la propia convocatoria
        for player in call.players.filter(id__in=[i for i in selected_players_ids if i.isdigit()]):
            Penalty.objects.create(
                player = player,
                reason = "Advertencia en el partido " + match.local.name + " VS " + match.visiting.name + ".",
                call = call
            )

        return redirect("call_for_match", match.id)
    return redirect("call_for_match", match.id)
