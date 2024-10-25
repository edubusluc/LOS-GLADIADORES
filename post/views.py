from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Post, Image
from .forms import PostForm
from match.models import Match
from django.contrib import messages

def home(request):
    posts = Post.objects.prefetch_related('images').all().order_by('-created_at')
    return render(request, 'home.html', {'posts': posts})


@login_required
def create_post(request):
    matches = Match.objects.filter(draft_mode=False)
    if request.method == 'POST':
        form = PostForm(request.POST)
        files = request.FILES.getlist('images')  # Obtener los archivos subidos

        # Verificar si el formulario es válido
        if form.is_valid():
            if not files:  # Si no hay imágenes
                messages.error(request, 'Debes seleccionar al menos una imagen')
                return render(request, 'create_post.html', {  # Volver a renderizar con el mensaje de error
                    'post_form': form,
                    'matches': matches
                })

            post = form.save(commit=False)

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
            # Aquí puedes manejar los errores del formulario si es necesario
            messages.error(request, 'Por favor corrige los errores en el formulario.')

    else:
        form = PostForm()

    return render(request, 'create_post.html', {
        'post_form': form,
        'matches': matches
    })
