from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
import hashlib

User = settings.AUTH_USER_MODEL


# =========================
# Helpers
# =========================
def gravatar_url(email: str, size: int = 200) -> str:
    mail = (email or "").strip().lower().encode("utf-8")
    md5 = hashlib.md5(mail).hexdigest()
    return f"https://www.gravatar.com/avatar/{md5}?s={size}&d=identicon"


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


# =========================
# Perfil de usuario
# =========================
class Profile(TimeStamped):
    """
    Datos extendidos del usuario final.
    """
    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)

    # Media
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    # Datos
    dni = models.CharField("DNI", max_length=20, blank=True, default="")
    telefono = models.CharField("Teléfono", max_length=30, blank=True, default="")
    birth_date = models.DateField("Fecha de nacimiento", null=True, blank=True)
    address = models.CharField("Dirección", max_length=255, blank=True, default="")
    postal_code = models.CharField("Código postal", max_length=12, blank=True, default="")

    def __str__(self):
        return f"Perfil de {getattr(self.user, 'username', 'user')}"

    @property
    def avatar_url(self) -> str:
        """
        Devuelve URL del avatar subido; si no existe, usa Gravatar del email del usuario.
        """
        try:
            if self.avatar and hasattr(self.avatar, "url"):
                return self.avatar.url
        except Exception:
            pass
        email = getattr(self.user, "email", "")
        return gravatar_url(email, size=200)


# Crear Profile automáticamente al crear un User
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


# =========================
# Cursos / Etapas / Lecciones
# =========================
class Course(models.Model):
    KIND_CHOICES = (
        ("course", "Curso"),
        ("training", "Capacitación"),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price_ars = models.PositiveIntegerField(default=0)
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # NUEVO: tipo de contenido
    kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default="course",
        help_text="Diferencia si es Curso o Capacitación."
    )

    def __str__(self):
        return self.title


class Stage(TimeStamped):
    course = models.ForeignKey(Course, related_name='stages', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    slug = models.SlugField()
    order = models.PositiveIntegerField(default=1)
    price_ars = models.DecimalField(max_digits=12, decimal_places=2)
    # PDF general (opcional): usar Drive /preview o link directo
    pdf_url = models.URLField(blank=True)

    class Meta:
        unique_together = ('course', 'slug')
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} — Etapa {self.order}: {self.title}"


class Lesson(TimeStamped):
    stage = models.ForeignKey(Stage, related_name='lessons', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    youtube_url = models.URLField(blank=True)
    # PDF por clase (opcional)
    pdf_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


# =========================
# Evaluaciones
# =========================
class Quiz(TimeStamped):
    stage = models.OneToOneField(Stage, related_name='quiz', on_delete=models.CASCADE)
    # Tu regla: 80% y sin límite (0 = ilimitado)
    passing_score = models.PositiveIntegerField(default=80, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_attempts = models.PositiveIntegerField(default=0)  # 0 = sin límite

    def __str__(self):
        return f"Quiz de {self.stage}"


class Question(TimeStamped):
    quiz = models.ForeignKey(Quiz, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField()

    def __str__(self):
        return self.text[:60]


class Choice(TimeStamped):
    question = models.ForeignKey(Question, related_name='choices', on_delete=models.CASCADE)
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text[:60]


class Enrollment(TimeStamped):
    user = models.ForeignKey(User, related_name='enrollments', on_delete=models.CASCADE)
    course = models.ForeignKey(Course, related_name='enrollments', on_delete=models.CASCADE)
    started_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'course')


class StageProgress(TimeStamped):
    user = models.ForeignKey(User, related_name='stage_progress', on_delete=models.CASCADE)
    stage = models.ForeignKey(Stage, related_name='progresses', on_delete=models.CASCADE)
    passed = models.BooleanField(default=False)
    score = models.PositiveIntegerField(default=0)
    passed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'stage')


class QuizAttempt(TimeStamped):
    user = models.ForeignKey(User, related_name='quiz_attempts', on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, related_name='attempts', on_delete=models.CASCADE)
    score = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']


# =========================
# Ventas
# =========================
class Bundle(TimeStamped):
    """Curso completo: agrupa todas las etapas de un curso."""
    course = models.ForeignKey(Course, related_name='bundles', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    price_ars = models.DecimalField(max_digits=12, decimal_places=2)
    stages = models.ManyToManyField(Stage, related_name='bundles')

    def __str__(self):
        return f"Bundle {self.title} ({self.course})"


class Purchase(TimeStamped):
    STATUS = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    PAYMENT_METHODS = (
        ('mp', 'Mercado Pago'),
        ('transfer', 'Transferencia'),
    )

    user = models.ForeignKey(User, related_name='purchases', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    external_ref = models.CharField(max_length=120, blank=True)  # ID MercadoPago/Stripe
    total_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # NUEVOS CAMPOS (para checkout)
    payment_method = models.CharField(
        max_length=12, choices=PAYMENT_METHODS, blank=True, default='',
        help_text="Método elegido por el usuario en el checkout."
    )
    transfer_receipt = models.FileField(
        upload_to='receipts/', null=True, blank=True,
        help_text="Comprobante de pago en caso de transferencia."
    )

    def __str__(self):
        return f"Purchase #{self.id} ({self.status})"


class PurchaseItem(TimeStamped):
    TYPE = (
        ('stage', 'Stage'),
        ('bundle', 'Bundle'),
    )
    purchase = models.ForeignKey(Purchase, related_name='items', on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=TYPE)
    stage = models.ForeignKey(Stage, null=True, blank=True, on_delete=models.CASCADE)
    bundle = models.ForeignKey(Bundle, null=True, blank=True, on_delete=models.CASCADE)
    price_ars = models.DecimalField(max_digits=12, decimal_places=2)


class Entitlement(TimeStamped):
    """
    Acceso otorgado a una etapa (por compra individual o por bundle).
    OJO: El prerrequisito de aprobar etapa anterior se valida aparte.
    """
    user = models.ForeignKey(User, related_name='entitlements', on_delete=models.CASCADE)
    stage = models.ForeignKey(Stage, related_name='entitlements', on_delete=models.CASCADE)
    source = models.CharField(max_length=20, default='stage')  # 'stage' o 'bundle'

    class Meta:
        unique_together = ('user', 'stage')
