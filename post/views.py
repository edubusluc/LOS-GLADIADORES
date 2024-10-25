from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Post, Image
from .forms import PostForm
from match.models import Match

def home(request):
    posts = Post.objects.prefetch_related('images').all().order_by('-created_at')
    return render(request, 'home.html', {'posts': posts})


@login_required
def create_post(request):
    matches = Match.objects.filter(draft_mode=False)
    if request.method == 'POST':
        post_form = PostForm(request.POST)
        files = request.FILES.getlist('images')  # Obtener los archivos subidos

        if post_form.is_valid() and files:
            post = post_form.save(commit=False)

            match_id = request.POST.get('match_id')  # Obtener el ID del partido seleccionado
            if match_id:
                try:
                    match = Match.objects.get(id=match_id)
                    post.content = f"{match.result}, en el partido {match.local} vs {match.visiting} con resultado final: {match.result_points}"
                except Match.DoesNotExist:
                    post.content = "Partido no válido."

            post.save()

            # Guardar cada imagen asociada a la publicación
            for file in files:
                Image.objects.create(post=post, image=file)

            return redirect('home')
    else:
        post_form = PostForm()

    return render(request, 'create_post.html', {
        'post_form': post_form,
        'matches': matches
    })
