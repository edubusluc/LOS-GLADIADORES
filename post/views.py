from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Post
from .forms import PostForm
from match.models import Match

def home(request):
    posts = Post.objects.all().order_by('-created_at')
    return render(request, 'home.html', {'posts': posts})


@login_required
def create_post(request):
    matches = Match.objects.filter(draft_mode=False)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        match_id = request.POST.get('match_id')  # Obtener el ID del partido seleccionado
        if form.is_valid():
            post = form.save(commit=False)

            if match_id:  # Si se ha seleccionado un partido
                try:
                    match = Match.objects.get(id=match_id)
                    post.content = f"{match.result}, en el partido {match.local} vs {match.visiting} con resultado final: {match.result_points}"  # O la lógica que desees para crear el contenido
                except Match.DoesNotExist:
                    post.content = "Partido no válido."  # Manejo de errores si es necesario
            
            post.save()
            return redirect('home')
    else:
        form = PostForm()
    return render(request, 'create_post.html', {'form': form, "matches": matches})
