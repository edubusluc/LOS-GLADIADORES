import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'snp_gladiadores.settings')
django.setup()

from django.apps import apps

def delete_all_data():
    for model in apps.get_models():
        model.objects.all().delete()

if __name__ == "__main__":
    delete_all_data()
    print("Todos los datos han sido eliminados.")
