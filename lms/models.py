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
    pdf_url = models.URLField(blank=True)
    pdf_file = models.FileField(upload_to="stage_pdfs/", null=True, blank=True)

    @property
    def pdf_src(self):
        if self.pdf_file:
            return self.pdf_file.url
        return self.pdf_url

    class Meta:
        unique_together = ('course', 'slug')
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} — Etapa {self.order}: {self.title}"


class Lesson(TimeStamped):
    stage = models.ForeignKey(Stage, related_name='lessons', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    youtube_url = models.URLField(blank=True)
    pdf_url = models.URLField(blank=True)
    pdf_file = models.FileField(upload_to="lesson_pdfs/", null=True, blank=True)
    order = models.PositiveIntegerField(default=1)

    @property
    def pdf_src(self):
        if self.pdf_file:
            return self.pdf_file.url
        return self.pdf_url

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
    certificate_issued_at = models.DateTimeField(null=True, blank=True)

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

# =========================
# TIENDA DE PRODUCTOS
# =========================

class ProductCategory(TimeStamped):
    name = models.CharField("Nombre", max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.name


class Product(TimeStamped):
    name        = models.CharField("Nombre", max_length=200)
    slug        = models.SlugField(unique=True)
    description = models.TextField("Descripción", blank=True)
    price_ars   = models.DecimalField("Precio (ARS)", max_digits=12, decimal_places=2)
    stock       = models.PositiveIntegerField("Stock", default=0)
    image       = models.ImageField("Imagen", upload_to="products/", null=True, blank=True)
    image_url   = models.URLField("URL de imagen (alternativa)", blank=True)
    category    = models.ForeignKey(
        ProductCategory, related_name="products",
        null=True, blank=True, on_delete=models.SET_NULL
    )
    is_active   = models.BooleanField("Activo", default=True)

    # Datos logísticos para cálculo de envío
    weight_kg   = models.DecimalField("Peso (kg)", max_digits=8, decimal_places=3, default=0)
    width_cm    = models.DecimalField("Ancho (cm)", max_digits=8, decimal_places=1, default=0)
    height_cm   = models.DecimalField("Alto (cm)",  max_digits=8, decimal_places=1, default=0)
    depth_cm    = models.DecimalField("Prof. (cm)", max_digits=8, decimal_places=1, default=0)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def image_display(self):
        """Devuelve URL de imagen (archivo o URL externa)."""
        try:
            if self.image and hasattr(self.image, "url"):
                return self.image.url
        except Exception:
            pass
        return self.image_url or ""

    @property
    def volumetric_weight(self):
        """Peso volumétrico = (L×A×P) / 5000 — estándar courier."""
        try:
            vol = (self.width_cm * self.height_cm * self.depth_cm) / 5000
            return float(vol)
        except Exception:
            return 0.0

    @property
    def billable_weight(self):
        return max(float(self.weight_kg), self.volumetric_weight)


class ShippingZone(TimeStamped):
    name        = models.CharField("Zona", max_length=100)
    multiplier  = models.DecimalField("Multiplicador", max_digits=4, decimal_places=2, default=1)
    postal_codes = models.TextField(
        "Códigos postales (separados por coma)",
        blank=True,
        help_text="Ej: 1000,1001,1002,1100"
    )

    class Meta:
        verbose_name = "Zona de envío"
        verbose_name_plural = "Zonas de envío"
        ordering = ["multiplier"]

    def __str__(self):
        return f"{self.name} (x{self.multiplier})"

    def codes_list(self):
        return [c.strip() for c in self.postal_codes.split(",") if c.strip()]


class ShippingConfig(TimeStamped):
    """Singleton — siempre hay una sola fila (id=1)."""
    base_rate_ars   = models.DecimalField("Tarifa base (ARS)", max_digits=10, decimal_places=2, default=500)
    per_kg_ars      = models.DecimalField("$ por kg", max_digits=8, decimal_places=2, default=150)
    free_over_ars   = models.DecimalField("Envío gratis desde (ARS)", max_digits=12, decimal_places=2, default=15000)
    # Proveedor externo (para integración futura)
    provider_name   = models.CharField("Proveedor", max_length=100, blank=True, default="Andreani")
    provider_url    = models.URLField("URL del proveedor", blank=True)
    provider_api_key = models.CharField("API Key", max_length=255, blank=True)
    provider_active = models.BooleanField("Integración activa", default=False)

    class Meta:
        verbose_name = "Configuración de envíos"

    def __str__(self):
        return "Configuración de envíos"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def calc_shipping(self, cart_items, postal_code: str) -> int:
        """
        cart_items: lista de dicts con {'product': Product, 'qty': int}
        Retorna costo en ARS (int). 0 = envío gratis.
        """
        subtotal = sum(float(i["product"].price_ars) * i["qty"] for i in cart_items)
        if subtotal >= float(self.free_over_ars):
            return 0

        # Zona según código postal
        zone = None
        for z in ShippingZone.objects.all():
            if postal_code in z.codes_list():
                zone = z
                break
        # Si no matchea ninguna zona → zona "Interior" (la de mayor multiplicador)
        if zone is None:
            zone = ShippingZone.objects.order_by("-multiplier").first()

        multiplier = float(zone.multiplier) if zone else 2.0

        total_bw = sum(i["product"].billable_weight * i["qty"] for i in cart_items)
        cost = (float(self.base_rate_ars) + total_bw * float(self.per_kg_ars)) * multiplier
        return max(0, round(cost))


class StoreOrder(TimeStamped):
    STATUS = (
        ("pending",    "Pendiente"),
        ("paid",       "Pagado"),
        ("shipped",    "Enviado"),
        ("delivered",  "Entregado"),
        ("cancelled",  "Cancelado"),
    )
    PAYMENT_METHODS = (
        ("mp",       "Mercado Pago"),
        ("transfer", "Transferencia"),
        ("cash",     "Efectivo"),
    )

    user            = models.ForeignKey(User, related_name="store_orders", on_delete=models.CASCADE)
    status          = models.CharField(max_length=12, choices=STATUS, default="pending")
    payment_method  = models.CharField(max_length=12, choices=PAYMENT_METHODS, blank=True)

    # Datos de entrega
    recipient_name  = models.CharField("Destinatario", max_length=200)
    email           = models.EmailField("Email")
    phone           = models.CharField("Teléfono", max_length=30, blank=True)
    address         = models.CharField("Dirección", max_length=300)
    city            = models.CharField("Ciudad", max_length=100)
    province        = models.CharField("Provincia", max_length=100)
    postal_code     = models.CharField("Código postal", max_length=12)

    # Montos
    subtotal_ars    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_ars    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_ars    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_ars       = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Tracking
    tracking_number = models.CharField("Número de seguimiento", max_length=100, blank=True)
    tracking_url    = models.URLField("URL de seguimiento", blank=True)
    notes           = models.TextField("Notas internas", blank=True)

    # Comprobante transferencia
    transfer_receipt = models.FileField(upload_to="store_receipts/", null=True, blank=True)

    class Meta:
        verbose_name = "Pedido tienda"
        verbose_name_plural = "Pedidos tienda"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido #{self.id} — {self.recipient_name} ({self.status})"


class StoreOrderItem(TimeStamped):
    order       = models.ForeignKey(StoreOrder, related_name="items", on_delete=models.CASCADE)
    product     = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    qty         = models.PositiveIntegerField(default=1)
    unit_price  = models.DecimalField(max_digits=12, decimal_places=2)  # precio al momento de compra

    def __str__(self):
        return f"{self.qty}x {self.product.name}"

    @property
    def subtotal(self):
        return self.unit_price * self.qty
