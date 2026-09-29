from django.shortcuts import redirect, get_object_or_404
from core.decorators import club_admin_required
from .models import Call

# Create your views here.
@club_admin_required
def delete_call(request, match_id):
    call = get_object_or_404(Call, match__id=match_id, match__club=request.club)
    if request.method == 'POST':
        call.delete()
        return redirect('call_for_match',match_id)

    return redirect('list_match')
