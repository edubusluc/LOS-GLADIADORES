from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title','content']

    def __init__(self, *args, **kwargs):
        super(PostForm, self).__init__(*args, **kwargs)
        self.fields['title'].label = "Título de la Publicación"
        self.fields['content'].label = "Contenido"
        self.fields['content'].widget.attrs.update({
            'placeholder': 'Añade una descripción personalizada'  # Añadir el placeholder aquí
        }) 

