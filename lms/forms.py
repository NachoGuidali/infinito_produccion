# lms/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from datetime import date
from django.contrib.auth.forms import AuthenticationForm

from .models import Profile  # <— antes decía UserProfile

User = get_user_model()

class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Email o usuario")

def _build_username_from_email(email: str) -> str:
    base = slugify(email.split("@")[0]) or "user"
    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base}-{i}"
    return username

class QuizForm(forms.Form):
    def __init__(self, *args, quiz=None, **kwargs):
        super().__init__(*args, **kwargs)
        if quiz is None:
            return
        for q in quiz.questions.all():
            field_name = f"q_{q.id}"
            choices = [(c.id, c.text) for c in q.choices.all()]
            self.fields[field_name] = forms.ChoiceField(
                label=q.text, choices=choices, widget=forms.RadioSelect
            )

class SignupForm(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name  = forms.CharField(label="Apellido", max_length=150)
    email      = forms.EmailField(label="Email")
    password1  = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2  = forms.CharField(label="Repetí la contraseña", widget=forms.PasswordInput)

    # Perfil
    dni              = forms.CharField(label="DNI", max_length=32)
    telefono         = forms.CharField(label="Teléfono", max_length=40)
    fecha_nacimiento = forms.DateField(label="Fecha de nacimiento", widget=forms.DateInput(attrs={"type": "date"}))
    direccion        = forms.CharField(label="Dirección", max_length=255, required=False)
    codigo_postal    = forms.CharField(label="Código postal", max_length=20, required=False,
                                       widget=forms.TextInput(attrs={"inputmode": "numeric"}))
    avatar           = forms.ImageField(label="Foto de perfil", required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("Ya existe una cuenta con este email.")
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1") or ""
        p2 = self.cleaned_data.get("password2") or ""
        if p1 != p2:
            raise ValidationError("Las contraseñas no coinciden.")
        if len(p1) < 6:
            raise ValidationError("La contraseña debe tener al menos 6 caracteres.")
        return p2

    def clean_fecha_nacimiento(self):
        fn = self.cleaned_data["fecha_nacimiento"]
        if fn >= date.today():
            raise ValidationError("La fecha de nacimiento no puede ser en el futuro.")
        return fn

    def save(self, request=None, *, create_inactive: bool = True):
        data = self.cleaned_data
        email = data["email"].lower()

        if getattr(User, "USERNAME_FIELD", "username") == "username":
            username = _build_username_from_email(email)
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=data["first_name"].strip(),
                last_name=data["last_name"].strip(),
                password=data["password1"],
            )
        else:
            user = User.objects.create_user(
                email=email,
                first_name=data["first_name"].strip(),
                last_name=data["last_name"].strip(),
                password=data["password1"],
            )

        if create_inactive:
            user.is_active = False
            user.save(update_fields=["is_active"])

        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                "dni": data["dni"].strip(),
                "telefono": data["telefono"].strip(),
                "birth_date": data["fecha_nacimiento"],
                "address": data.get("direccion", "").strip(),
                "postal_code": data.get("codigo_postal", "").strip(),
            }
        )

        # Si ya existía, actualizamos campos (por si se había creado “vacío”)
        if not created:
            profile.dni = data["dni"].strip()
            profile.telefono = data["telefono"].strip()
            profile.birth_date = data["fecha_nacimiento"]
            profile.address = data.get("direccion", "").strip()
            profile.postal_code = data.get("codigo_postal", "").strip()
            profile.save(update_fields=["dni","telefono","birth_date","address","postal_code"])

        avatar = data.get("avatar")
        if avatar:
            profile.avatar = avatar
            profile.save(update_fields=["avatar"])

        return user


class ProfileSettingsForm(forms.ModelForm):
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name  = forms.CharField(label="Apellido", max_length=150)
    email      = forms.EmailField(label="Email")

    class Meta:
        model  = Profile
        fields = ("dni", "telefono", "birth_date", "address", "postal_code", "avatar")
        widgets = {
            "birth_date":  forms.DateInput(attrs={"type": "date"}),
            "postal_code": forms.TextInput(attrs={"inputmode": "numeric"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial  = user.last_name
            self.fields["email"].initial      = user.email

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email=email)
        if self._user:
            qs = qs.exclude(pk=self._user.pk)
        if qs.exists():
            raise ValidationError("Ya existe una cuenta con este email.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self._user:
            self._user.first_name = self.cleaned_data["first_name"].strip()
            self._user.last_name  = self.cleaned_data["last_name"].strip()
            self._user.email      = self.cleaned_data["email"].strip().lower()
            self._user.save(update_fields=["first_name", "last_name", "email"])
        if commit:
            profile.save()
        return profile
