from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from players.models import *
from match.models import *
from .models import *

# Create your views here.
def delete_call(request, match_id):
    call = get_object_or_404(Call, match__id=match_id)
    if request.method == 'POST':
        call.delete()
        return redirect('call_for_match',match_id)

    return redirect('list_match')