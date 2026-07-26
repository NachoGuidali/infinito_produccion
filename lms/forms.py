# lms/forms.py
import re
import time

from django import forms
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from datetime import date
from django.contrib.auth.forms import AuthenticationForm

from .models import Profile  # <— antes decía UserProfile

User = get_user_model()

# Antibot del registro. Entre ene y may 2026 entraron ~1450 cuentas automaticas
# que rellenaban TODOS los campos con 10 letras al azar (dni='rshjmrrqdt'),
# telefono '+1-...' y fecha de nacimiento en el futuro. Cada una disparaba un
# mail de activacion a una direccion real ajena, usando el sitio como relay.
_HONEYPOT_SALT = "lms.signup.hp"
_MIN_SEGUNDOS_FORMULARIO = 3   # un humano no completa 10 campos en menos
_EDAD_MINIMA = 14              # el alumno real mas joven tiene 15 (nacido 2010)

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

    # ── Antibot ──
    # Campo trampa: invisible para el usuario, los bots que rellenan todo lo llenan.
    sitio_web = forms.CharField(
        required=False, label="",
        widget=forms.TextInput(attrs={
            "tabindex": "-1", "autocomplete": "off", "aria-hidden": "true",
            "style": "position:absolute;left:-9999px;width:1px;height:1px;opacity:0",
        }),
    )
    # Marca de tiempo firmada: mide cuánto tardó en completar el formulario.
    ts = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Al mostrar el formulario vacío, sellamos el momento de apertura.
        if not self.is_bound:
            self.fields["ts"].initial = signing.dumps(time.time(), salt=_HONEYPOT_SALT)

    def clean_sitio_web(self):
        if (self.cleaned_data.get("sitio_web") or "").strip():
            raise ValidationError("No pudimos validar el formulario. Recargá la página.")
        return ""

    def clean_ts(self):
        raw = self.cleaned_data.get("ts") or ""
        if not raw:
            raise ValidationError("Recargá la página y completá el formulario de nuevo.")
        try:
            abierto = signing.loads(raw, salt=_HONEYPOT_SALT, max_age=60 * 60 * 6)
        except signing.SignatureExpired:
            raise ValidationError("El formulario expiró. Recargá la página.")
        except signing.BadSignature:
            raise ValidationError("No pudimos validar el formulario. Recargá la página.")
        if time.time() - float(abierto) < _MIN_SEGUNDOS_FORMULARIO:
            raise ValidationError("Enviaste el formulario demasiado rápido. Intentá de nuevo.")
        return raw

    def clean_dni(self):
        # Los 149 DNI reales son 8 dígitos; los bots ponían 10 letras.
        dni = (self.cleaned_data.get("dni") or "").strip()
        limpio = re.sub(r"[.\s-]", "", dni)
        if not limpio.isdigit():
            raise ValidationError("El DNI debe tener solo números.")
        if not (7 <= len(limpio) <= 9):
            raise ValidationError("El DNI debe tener entre 7 y 9 dígitos.")
        return limpio

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
        hoy = date.today()
        if fn >= hoy:
            raise ValidationError("La fecha de nacimiento no puede ser en el futuro.")
        # Los bots nacían entre 2023 y 2026. El alumno real más joven nació en 2010.
        edad = hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
        if edad < _EDAD_MINIMA:
            raise ValidationError("Revisá la fecha de nacimiento.")
        if edad > 110:
            raise ValidationError("Revisá la fecha de nacimiento.")
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
