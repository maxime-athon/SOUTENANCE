# core/forms.py
from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import UserProfile

class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Laissez vide pour conserver le mot de passe actuel."
    )
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label='Rôle')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].required = True
        self.fields['username'].widget.attrs.update({
            'class': 'form-control rounded-3',
            'placeholder': 'Ex. amedee',
            'autocomplete': 'username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control rounded-start-3',
            'placeholder': 'Au moins 8 caractères',
            'autocomplete': 'new-password',
        })
        self.fields['role'].widget.attrs.update({'class': 'form-select rounded-3'})
        if self.instance and self.instance.pk:
            profile, _ = UserProfile.objects.get_or_create(user=self.instance)
            self.fields['role'].initial = profile.role
        else:
            self.fields['password'].required = True
            self.fields['password'].help_text = 'Mot de passe requis pour créer le compte.'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            try:
                validate_password(password, self.instance)
            except ValidationError as error:
                raise forms.ValidationError(error.messages)
        return password

    def save(self, commit=True):
        """Save a usable password, the business role and its matching group."""
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)

        role = self.cleaned_data['role']
        user.is_staff = role in {'ADMIN', 'ARCHIVISTE'}

        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save(update_fields=['role', 'updated_at'])

            role_groups = {
                'ADMIN': 'Admin',
                'ARCHIVISTE': 'Archiviste',
                'JOURNALISTE': 'Journaliste',
                'LECTEUR': 'Lecteur',
            }
            groups = {
                name: Group.objects.get_or_create(name=name)[0]
                for name in role_groups.values()
            }
            user.groups.remove(*groups.values())
            user.groups.add(groups[role_groups[role]])

        return user
