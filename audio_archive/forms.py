from django import forms
from .models import Category, AudioFile, Language

# "Formulaires pour les modèles Category et AudioFile"
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class AudioFileForm(forms.ModelForm):
    class Meta:
        model = AudioFile
        fields = [
            'category', 'language', 'band_number', 'recording_number', 
            'title', 'subtitle', 'description', 'producer', 
            'recording_date', 'duration', 'speed', 'broadcast_date', 
            'file', 'is_featured'
        ]
        
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'band_number': forms.TextInput(attrs={'class': 'form-control'}),
            'recording_number': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'producer': forms.TextInput(attrs={'class': 'form-control'}),
            'recording_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'broadcast_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM:SS'}),
            'speed': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'id': 'id_file'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

#permet de ne pas rendre le champ file obligatoire lors de l'édition d'un AudioFile existant
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['file'].required = False

#pour éviter l'erreur d'extension du fichier .zip déjà stocké en base lors de l'édition d'un AudioFile existant(pas trop utilsiser j'ai finalement autorier les fichiers .zip)
    def clean(self):
        cleaned_data = super().clean()
        # Si on est en mode édition et qu'aucun nouveau fichier n'est envoyé
        if self.instance and self.instance.pk and not self.cleaned_data.get('file'):
            # Ignorer l'erreur d'extension liée au fichier .zip déjà stocké en base
            if 'file' in self._errors:
                del self._errors['file']
        return cleaned_data