from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Post, Image
from .forms import PostForm
from match.models import Match
from django.contrib import messages
from django.core.paginator import Paginator


def home(request):
    posts = Post.objects.prefetch_related('images').all().order_by('-created_at')
    
    # Configuración de la paginación
    paginator = Paginator(posts, 3)  # 3 publicaciones por página
    page_number = request.GET.get('page')  # Obtiene el número de página desde la URL
    page_obj = paginator.get_page(page_number)  # Paginación de los posts

    return render(request, 'home.html', {'page_obj': page_obj})


@login_required
def create_post(request):
    matches = Match.objects.filter(draft_mode=False)

    if request.method == 'POST':
        form = PostForm(request.POST)
        files = request.FILES.getlist('images')

        # Validar el formulario
        if form.is_valid():
            if not files:
                return handle_error(request, form, matches, 'Debes seleccionar al menos una imagen')

            post = form.save(commit=False)
            
            match_id = request.POST.get('match_id')
            if match_id:
                post.content = generate_post_content(match_id)  # Generar contenido desde el partido
            else:
                post.content = form.cleaned_data['content']  # Usar el contenido del formulario si no hay partido

            post.save()
            save_post_images(post, files)

            return redirect('home')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')

    else:
        form = PostForm()

    return render(request, 'create_post.html', {
        'post_form': form,
        'matches': matches
    })

def handle_error(request, form, matches, error_message):
    messages.error(request, error_message)
    return render(request, 'create_post.html', {
        'post_form': form,
        'matches': matches
    })

def generate_post_content(match_id):
    if match_id:
        try:
            match = Match.objects.get(id=match_id)
            return f"{match.result}, en el partido {match.local} vs {match.visiting} con resultado final: {match.result_points}"
        except Match.DoesNotExist:
            return "Partido no válido."
    return ""

def save_post_images(post, files):
    for file in files:
        Image.objects.create(post=post, image=file)
