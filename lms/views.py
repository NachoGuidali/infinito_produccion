from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout, get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q, Count, Max
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.core.mail import send_mail
from django.core import signing
from django.conf import settings

import time
import hashlib
from decimal import Decimal
from datetime import date

import mercadopago

from .models import (
    Course,
    Stage,
    Lesson,
    Quiz,
    QuizAttempt,
    StageProgress,
    Bundle,
    Entitlement,
    Purchase,
    Profile,
)
from .forms import QuizForm, SignupForm, LoginForm
from .services.access import can_view_stage
from .services.payments import (
    create_checkout,
    mark_paid_and_grant,
    create_mp_preference_for_purchase,
)
from django.contrib.auth.views import LoginView


class CustomLoginView(LoginView):
    authentication_form = LoginForm
# =======================
# Helpers (avatar + gravatar + activación)
# =======================
def _gravatar_url(email: str, size: int = 200) -> str:
    mail = (email or "").strip().lower().encode("utf-8")
    md5 = hashlib.md5(mail).hexdigest()
    return f"https://www.gravatar.com/avatar/{md5}?s={size}&d=identicon"


def _avatar_url_for(user):
    """Usa el avatar del Profile si existe; si no, Gravatar."""
    try:
        prof = getattr(user, "profile", None)
        if prof:
            return prof.avatar_url
    except Exception:
        pass
    return _gravatar_url(user.email, 200)


_SIGN_SALT = "lms.signup.email"


def _make_activation_token(user):
    payload = {"uid": user.pk, "email": user.email}
    return signing.dumps(payload, salt=_SIGN_SALT)


def _load_activation_token(token, max_age_days=7):
    return signing.loads(token, salt=_SIGN_SALT, max_age=max_age_days * 24 * 3600)


def _send_activation_email(request, user):
    token = _make_activation_token(user)
    url = request.build_absolute_uri(reverse("lms:signup_confirm", args=[token]))
    subject = "Confirmá tu cuenta"
    message = (
        f"Hola {user.first_name or user.username},\n\n"
        f"Gracias por registrarte en Infinito Capacitaciones.\n"
        f"Para activar tu cuenta hacé clic en el siguiente enlace:\n\n{url}\n\n"
        f"Si no te registraste vos, ignorá este correo."
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    #send_mail(subject, message, None, [user.email], fail_silently=True)


# =======================
# LOGOUT
# =======================
def logout_view(request):
    logout(request)
    return redirect("lms:home")


# =======================
# HOME
# =======================
def home(request):
    if not request.user.is_authenticated:
        return render(request, "lms/home_public.html")
    courses = (
        Course.objects.filter(kind="course").prefetch_related("stages").order_by("id")
    )
    trainings = (
        Course.objects.filter(kind="training")
        .prefetch_related("stages")
        .order_by("id")
    )
    return render(
        request,
        "lms/home_logged.html",
        {
            "courses": courses,
            "trainings": trainings,
        },
    )


# =======================
# SIGNUP (registro + confirmación)
# =======================
def signup(request):
    if request.user.is_authenticated:
        return redirect("lms:home")

    if request.method == "POST":
        form = SignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(
                request=request, create_inactive=True
            )  # crea user inactivo + Profile
            _send_activation_email(request, user)
            return redirect("lms:signup_done")
    else:
        form = SignupForm()

    return render(request, "lms/signup.html", {"form": form})


def signup_done(request):
    return render(request, "lms/signup_done.html")


def signup_confirm(request, token):
    try:
        data = _load_activation_token(token)
    except signing.BadSignature:
        messages.error(request, "El enlace de activación no es válido.")
        return redirect("login")
    except signing.SignatureExpired:
        messages.error(request, "El enlace de activación expiró. Registrate nuevamente.")
        return redirect("lms:signup")

    UserModel = get_user_model()
    user = UserModel.objects.filter(pk=data.get("uid"), email=data.get("email")).first()
    if not user:
        messages.error(request, "No se encontró el usuario para activar.")
        return redirect("login")

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, "¡Cuenta activada! Ya podés iniciar sesión.")
        return redirect("login")

    messages.info(request, "Tu cuenta ya estaba activa. Iniciá sesión.")
    return redirect("login")


# =======================
# CATÁLOGO Y CURSO
# =======================
def catalog(request):
    t = request.GET.get("type")
    qs = Course.objects.prefetch_related("stages").all()
    if t in ("course", "training"):
        qs = qs.filter(kind=t)
    return render(
        request,
        "lms/catalog.html",
        {
            "courses": qs,
            "current_type": t,
        },
    )


def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug)

    stages_qs = course.stages.all().prefetch_related("lessons").order_by("order")
    first_stage = stages_qs.first()

    # Entitlements + aprobaciones por etapa
    stage_entitled_ids = set()
    passed_by_id = set()
    course_owned = False
    course_completed = False

    if request.user.is_authenticated:
        stage_ids = set(stages_qs.values_list("id", flat=True))

        got = Entitlement.objects.filter(
            user=request.user, stage_id__in=stage_ids
        ).values_list("stage_id", flat=True)
        stage_entitled_ids = set(got)

        # Todas las etapas poseen entitlement => “comprado”
        if stage_ids and stage_ids.issubset(stage_entitled_ids):
            course_owned = True

        # Etapas aprobadas
        passed_by_id = set(
            StageProgress.objects.filter(
                user=request.user,
                passed=True,
                stage__course=course
            ).values_list("stage_id", flat=True)
        )

        # Curso “completado” si aprobó todas las etapas
        if stage_ids and stage_ids.issubset(passed_by_id):
            course_completed = True

    # Bundle(s)
    bundles = list(course.bundles.all()[:1])

    # Precio tachado (suma etapas) — ocultalo en template cuando kind=="training"
    try:
        stages_total_ars = sum(
            Decimal(getattr(s, "price_ars", 0) or 0) for s in stages_qs
        )
    except Exception:
        stages_total_ars = Decimal("0")

    # Capacitación (aplanado)
    training_payload = None
    if getattr(course, "kind", "") == "training":
        pdf_items, video_lessons, quiz_targets = [], [], []
        for st in stages_qs:
            has_access = course_owned or (
                request.user.is_authenticated and (st.id in stage_entitled_ids)
            )
            if not has_access:
                continue
            if getattr(st, "pdf_url", ""):
                pdf_items.append(
                    {
                        "title": f"{st.title} — Material",
                        "url": st.pdf_url,
                        "source": "stage",
                    }
                )
            for le in st.lessons.all():
                if getattr(le, "pdf_url", ""):
                    pdf_items.append(
                        {"title": le.title, "url": le.pdf_url, "source": "lesson"}
                    )
                if getattr(le, "youtube_url", ""):
                    video_lessons.append(le)
            # En CAPACITACIÓN el quiz no es obligatorio; si existe, lo listamos como opcional
            if Quiz.objects.filter(stage=st).exists():
                quiz_targets.append(
                    {
                        "title": st.title,
                        "url": reverse(
                            "lms:quiz_take",
                            args=[course.slug, st.slug],
                        ),
                    }
                )
        training_payload = {
            "pdf_items": pdf_items,
            "video_lessons": video_lessons,
            "quiz_targets": quiz_targets,
        }

    return render(
        request,
        "lms/course_detail.html",
        {
            "course": course,
            "bundles": bundles,
            "stage_entitled_ids": stage_entitled_ids,
            "passed_by_id": passed_by_id,
            "course_owned": course_owned,
            "course_completed": course_completed,
            "stages": stages_qs,
            "first_stage": first_stage,
            "stages_total_ars": stages_total_ars,
            "training_payload": training_payload,
        },
    )


# =======================
# DIPLOMA / CERTIFICADO DE CURSO (por ahora acceso directo)
# =======================
@login_required
def course_certificate(request, slug):
    course = get_object_or_404(Course, slug=slug)

    completion_date = timezone.now()
    full_name = (request.user.get_full_name() or request.user.username).strip()

    return render(
        request,
        "lms/course_certificate.html",
        {
            "course": course,
            "user_fullname": full_name,
            "completion_date": completion_date,
        },
    )


# =======================
# CARRITO (por sesión)
# =======================
def _cart(session):
    c = session.get("cart")
    if not isinstance(c, dict):
        c = {}
        session["cart"] = c
    return c


def _cart_key(item_type, item_id):
    return f"{item_type}:{int(item_id)}"


def _cart_item_payload(item_type, obj):
    """
    Para etapa: 'Etapa N — <etapa>' + course_title.
    Para bundle: 'Curso completo — <curso>' + course_title.
    """
    if item_type == "stage":
        num = getattr(obj, "order", None)
        prefix = f"Etapa {num}" if num is not None else "Etapa"
        title = f"{prefix} — {obj.title}"
        course_title = getattr(obj.course, "title", "")
        price = Decimal(obj.price_ars or 0)
    else:
        course_title = getattr(obj.course, "title", "")
        title = f"Curso completo — {course_title or obj.title}"
        price = Decimal(obj.price_ars or 0)
    return {
        "type": item_type,
        "id": obj.id,
        "title": title,
        "course_title": course_title,
        "price_ars": str(price),
    }


def _cart_totals(cart_dict):
    total = Decimal("0")
    for _, it in cart_dict.items():
        try:
            total += Decimal(it.get("price_ars", "0"))
        except Exception:
            pass
    return total


def cart_view(request):
    cart = _cart(request.session)
    items = [
        {
            "key": k,
            "type": it.get("type"),
            "id": it.get("id"),
            "title": it.get("title"),
            "course_title": it.get("course_title", ""),
            "price_ars": Decimal(it.get("price_ars", "0")),
        }
        for k, it in cart.items()
    ]
    total = _cart_totals(cart)
    return render(request, "lms/cart.html", {"items": items, "total_ars": total})


@require_POST
def cart_add(request):
    item_type = request.POST.get("type")
    item_id = request.POST.get("id")
    next_url = request.POST.get("next")  # para redirección forzada

    if item_type not in ("stage", "bundle"):
        return HttpResponse("Tipo inválido", status=400)
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return HttpResponse("ID inválido", status=400)

    obj = get_object_or_404(Stage if item_type == "stage" else Bundle, id=item_id)

    key = _cart_key(item_type, item_id)
    cart = _cart(request.session)
    cart[key] = _cart_item_payload(item_type, obj)
    request.session.modified = True

    messages.success(request, "Agregado al carrito.")
    if next_url:
        return redirect(next_url)
    return redirect(request.META.get("HTTP_REFERER", reverse("lms:cart_view")))


def cart_remove(request, key):
    cart = _cart(request.session)
    if key in cart:
        cart.pop(key)
        request.session.modified = True
        messages.success(request, "Item quitado del carrito.")
    return redirect(reverse("lms:cart_view"))


def cart_clear(request):
    request.session["cart"] = {}
    request.session.modified = True
    messages.success(request, "Carrito vaciado.")
    return redirect(reverse("lms:cart_view"))


@login_required
def cart_go_checkout(request):
    cart = _cart(request.session)
    if not cart:
        return redirect("lms:cart_view")

    items = [
        {
            "type": it["type"],
            "id": int(it["id"]),
            "price_ars": Decimal(it.get("price_ars", "0")),
        }
        for it in cart.values()
    ]

    purchase = create_checkout(request.user, items)
    request.session["cart"] = {}
    request.session.modified = True
    return redirect(f"{reverse('lms:checkout')}?pid={purchase.id}")


# =======================
# ETAPA Y QUIZ
# =======================
@login_required
def stage_detail(request, course_slug, stage_slug):
    stage = get_object_or_404(Stage, course__slug=course_slug, slug=stage_slug)
    ok, reason = can_view_stage(request.user, stage)
    if not ok:
        return render(
            request, "lms/stage_detail.html", {"stage": stage, "blocked_reason": reason}
        )

    sp = StageProgress.objects.filter(
        user=request.user, stage=stage, passed=True
    ).first()
    is_passed = bool(sp)

    lessons = stage.lessons.all()
    return render(
        request,
        "lms/stage_detail.html",
        {"stage": stage, "lessons": lessons, "is_passed": is_passed},
    )


@login_required
def quiz_take(request, course_slug, stage_slug):
    stage = get_object_or_404(Stage, course__slug=course_slug, slug=stage_slug)
    quiz = get_object_or_404(Quiz, stage=stage)

    ok, reason = can_view_stage(request.user, stage)
    if not ok:
        return HttpResponseForbidden(reason)

    if request.method == "POST":
        form = QuizForm(request.POST, quiz=quiz)
        if form.is_valid():
            total = quiz.questions.count()
            correct = 0
            for q in quiz.questions.all():
                choice_id = int(form.cleaned_data[f"q_{q.id}"])
                if q.choices.filter(id=choice_id, is_correct=True).exists():
                    correct += 1
            score = round((correct / max(total, 1)) * 100)
            passed = score >= quiz.passing_score

            QuizAttempt.objects.create(
                user=request.user, quiz=quiz, score=score, passed=passed
            )

            sp, _ = StageProgress.objects.get_or_create(
                user=request.user, stage=stage
            )
            sp.score = max(sp.score, score)
            if passed and not sp.passed:
                sp.passed = True
                sp.passed_at = timezone.now()
            sp.save()

            return render(
                request,
                "lms/quiz_result.html",
                {
                    "stage": stage,
                    "course": stage.course,
                    "quiz": quiz,
                    "score": score,
                    "passed": passed,
                    "passing_score": quiz.passing_score,
                    "retake_url": reverse(
                        "lms:quiz_take", args=[course_slug, stage_slug]
                    ),
                    "stage_url": reverse(
                        "lms:stage_detail", args=[course_slug, stage_slug]
                    ),
                    "profile_url": reverse("lms:profile"),
                },
            )
    else:
        form = QuizForm(quiz=quiz)

    return render(request, "lms/quiz_take.html", {"stage": stage, "quiz": quiz, "form": form})


# =======================
# CHECKOUT / WEBHOOK
# =======================
def _hydrate_purchase_display(purchase):
    """
    Adjunta en runtime:
      - purchase.payment_method (inferido)
      - purchase.transfer_receipt.url (si corresponde)
    """
    method = None
    receipt_url = None
    ref = purchase.external_ref or ""
    if ref.startswith("TRANSFER:"):
        method = "transfer"
        path = ref.split("TRANSFER:", 1)[1]
        try:
            receipt_url = default_storage.url(path)
        except Exception:
            receipt_url = None

    purchase.payment_method = method
    purchase.transfer_receipt = (
        type("R", (), {"url": receipt_url})() if receipt_url else None
    )
    return purchase


@login_required
def checkout_view(request):
    # POST: carga comprobante de transferencia
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "submit_transfer":
            try:
                pid = int(request.POST.get("purchase_id", "0"))
            except ValueError:
                return HttpResponse("purchase_id inválido", status=400)

            purchase = get_object_or_404(Purchase, id=pid)
            if purchase.user_id != request.user.id:
                return HttpResponseForbidden("No autorizado")

            up = request.FILES.get("receipt")
            if not up:
                messages.error(request, "Adjuntá el comprobante (PDF/JPG/PNG).")
                return redirect(f"{reverse('lms:checkout')}?pid={purchase.id}")

            safe_name = (
                f"receipts/purchase_{purchase.id}_{int(time.time())}_{slugify(up.name)}"
            )
            saved_path = default_storage.save(safe_name, up)

            purchase.external_ref = f"TRANSFER:{saved_path}"
            if purchase.status != "paid":
                purchase.status = "pending"
            purchase.save(update_fields=["external_ref", "status"])

            messages.success(
                request,
                "Tu comprobante fue enviado correctamente. "
                "Estamos validando la transferencia. Volvé a ingresar en unos minutos para acceder a tu curso.",
            )
            return redirect(f"{reverse('lms:checkout')}?pid={purchase.id}")

    # GET con pid (ya existe la compra)
    pid = request.GET.get("pid")
    if pid:
        try:
            pid = int(pid)
        except ValueError:
            return HttpResponse("purchase_id inválido", status=400)

        purchase = get_object_or_404(Purchase, id=pid)
        if purchase.user_id != request.user.id:
            return HttpResponseForbidden("No autorizado")

        _hydrate_purchase_display(purchase)
        _, init_point = create_mp_preference_for_purchase(purchase)
        return render(
            request,
            "lms/checkout.html",
            {
                "purchase": purchase,
                "mp_init_point": init_point,
            },
        )

    # GET inicial: viene con stage_id / bundle_id
    items = []
    stage_id = request.GET.get("stage_id")
    bundle_id = request.GET.get("bundle_id")

    if stage_id:
        items.append({"type": "stage", "id": int(stage_id), "price_ars": None})
    if bundle_id:
        items.append({"type": "bundle", "id": int(bundle_id), "price_ars": None})

    if not items:
        return HttpResponse("Seleccioná una etapa o el curso completo.")

    purchase = create_checkout(request.user, items)
    _hydrate_purchase_display(purchase)
    _, init_point = create_mp_preference_for_purchase(purchase)
    return render(
        request,
        "lms/checkout.html",
        {
            "purchase": purchase,
            "mp_init_point": init_point,
        },
    )


@csrf_exempt
def webhook_paid(request):
    """
    Webhook de pago.
    - Soporta:
        * Modo viejo: POST con purchase_id + external_ref (tests internos)
        * Modo real Mercado Pago: topic=payment, id=<payment_id>
    """
    # --- Modo test manual interno: POST con purchase_id ---
    if (
        request.method == "POST"
        and request.POST.get("purchase_id")
        and not (request.POST.get("topic") or request.POST.get("type"))
    ):
        purchase_id = request.POST.get("purchase_id")
        external_ref = request.POST.get("external_ref", "MANUAL")
        try:
            purchase = Purchase.objects.get(id=purchase_id)
        except Purchase.DoesNotExist:
            return HttpResponse(status=404)
        mark_paid_and_grant(purchase, external_ref)
        return HttpResponse("ok")

    # --- Notificación de Mercado Pago ---
    data = request.POST if request.method == "POST" else request.GET
    topic = data.get("topic") or data.get("type")

    if topic != "payment":
        # Podés expandir acá para merchant_order si lo necesitás
        return HttpResponse("ignored", status=200)

    payment_id = data.get("id") or data.get("data.id")
    if not payment_id:
        return HttpResponse("missing payment id", status=400)

    access_token = getattr(settings, "MP_ACCESS_TOKEN", "")
    if not access_token:
        return HttpResponse("mp token not configured", status=500)

    sdk = mercadopago.SDK(access_token)
    try:
        payment_info = sdk.payment().get(payment_id)
    except Exception:
        return HttpResponse("error contacting mp", status=500)

    body = payment_info.get("response", {}) if isinstance(payment_info, dict) else {}
    status = body.get("status")
    external_reference = body.get("external_reference")

    if not external_reference:
        return HttpResponse("no external_reference", status=400)

    if status in ("approved", "authorized"):
        try:
            purchase = Purchase.objects.get(id=int(external_reference))
        except (ValueError, Purchase.DoesNotExist):
            return HttpResponse("purchase not found", status=404)

        mark_paid_and_grant(purchase, external_ref=f"MP:{payment_id}")

    return HttpResponse("ok")


# ==============================
# PERFIL (resumen + compras)
# ==============================
# ==============================
# PERFIL (resumen + compras)
# ==============================
@login_required
def profile(request):
    user = request.user

    # Guardar cambios (User + Profile)
    if request.method == "POST":
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name  = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        if email:
            user.email = email
        user.save(update_fields=["first_name", "last_name", "email"])

        prof, _ = Profile.objects.get_or_create(user=user)
        prof.dni = request.POST.get("dni", "").strip()
        prof.telefono = request.POST.get("phone", "").strip()

        # birth_date (YYYY-MM-DD) — parse seguro
        bd = (request.POST.get("birthdate") or "").strip()
        if bd:
            try:
                y, m, d = map(int, bd.split("-"))
                prof.birth_date = date(y, m, d)
            except Exception:
                pass
        else:
            prof.birth_date = None

        prof.address = request.POST.get("address", "").strip()
        prof.postal_code = request.POST.get("postal_code", "").strip()

        up = request.FILES.get("avatar")
        if up:
            prof.avatar = up  # FileField: guarda archivo al hacer save()
        prof.save()
        messages.success(request, "Perfil actualizado.")
        return redirect("lms:profile")

    # Avatar visible (persistente)
    avatar_url = _avatar_url_for(user)

    # Cursos del usuario (vía etapas a las que tiene acceso)
    entitled_stage_ids = set(
        Entitlement.objects.filter(user=user).values_list("stage_id", flat=True)
    )
    course_ids = (
        Stage.objects.filter(id__in=entitled_stage_ids)
        .values_list("course_id", flat=True)
        .distinct()
    )
    my_courses = (
        Course.objects.filter(id__in=course_ids)
        .prefetch_related("stages", "stages__lessons")
        .order_by("title")
    )

    courses_data = []
    total_inscriptos = 0
    total_finalizados = 0
    failed_quizzes = QuizAttempt.objects.filter(user=user, passed=False).count()

    for course in my_courses:
        total_inscriptos += 1
        stages = list(course.stages.all().order_by("order"))
        stage_ids = [s.id for s in stages]

        passed_by_id = set(
            StageProgress.objects.filter(
                user=user, stage_id__in=stage_ids, passed=True
            ).values_list("stage_id", flat=True)
        )

        stages_info = []
        next_stage_to_study = None   # Etapa siguiente para CONTINUAR (ya comprada)
        next_stage_to_buy = None     # Etapa siguiente para COMPRAR (no tiene entitlement)

        for s in stages:
            entitled = s.id in entitled_stage_ids
            passed = s.id in passed_by_id
            url = (
                reverse("lms:stage_detail", args=[course.slug, s.slug])
                if entitled
                else None
            )

            stages_info.append(
                {
                    "obj": s,
                    "title": s.title,
                    "order": s.order,
                    "entitled": entitled,
                    "passed": passed,
                    "url": url,
                }
            )

            # Próxima etapa para continuar (ya comprada pero no aprobada)
            if (not passed) and entitled and (next_stage_to_study is None):
                next_stage_to_study = s

            # Próxima etapa para comprar (la primera sin entitlement)
            if (not entitled) and (next_stage_to_buy is None):
                next_stage_to_buy = s

        total = len(stages)
        passed_count = sum(1 for s in stages if s.id in passed_by_id)

        if total > 0 and passed_count == total:
            status = "aprobado"
        elif passed_count > 0:
            status = "en_progreso"
        else:
            status = "nuevo"

        if status == "aprobado":
            total_finalizados += 1

        # Para CAPACITACIONES: continuar lleva al curso completo (no etapas)
        next_url = None
        kind = getattr(course, "kind", "course")
        if kind == "training":
            next_url = reverse("lms:course_detail", args=[course.slug]) + "#contenido"
        elif next_stage_to_study:
            next_url = reverse(
                "lms:stage_detail", args=[course.slug, next_stage_to_study.slug]
            )

        courses_data.append(
            {
                "course": course,
                "kind": kind,
                "total": total,
                "passed": passed_count,
                "status": status,
                "next_stage_url": next_url,          # seguir estudiando
                "next_stage_to_buy": next_stage_to_buy,  # comprar siguiente etapa
                "stages_info": stages_info,
            }
        )

    total_en_progreso = sum(
        1 for d in courses_data if d["status"] in ("en_progreso", "nuevo")
    )

    # 👇 Compras del usuario + hidratar para ver transferencia / comprobante
    purchases_qs = (
        Purchase.objects.filter(user=user)
        .order_by("-created_at")
        .prefetch_related("items", "items__stage", "items__bundle")
    )
    purchases = [_hydrate_purchase_display(p) for p in purchases_qs]

    stats = {
        "inscriptos": total_inscriptos,
        "en_progreso": total_en_progreso,
        "finalizados": total_finalizados,
        "desaprobados": failed_quizzes,
    }

    # Extra visibles (para precargar form html actual)
    prof = Profile.objects.filter(user=user).first()
    extra = {
        "dni": getattr(prof, "dni", ""),
        "phone": getattr(prof, "telefono", ""),
        "birthdate": getattr(prof, "birth_date", ""),
        "address": getattr(prof, "address", ""),
        "postal_code": getattr(prof, "postal_code", ""),
    }

    return render(
        request,
        "lms/profile.html",
        {
            "avatar_url": avatar_url,
            "courses_data": courses_data,
            "purchases": purchases,
            "stats": stats,
            "extra": extra,
        },
    )


# ==================================
# PANEL ADMIN LIGERO + ACCIONES
# ==================================
def _is_staff(u):
    return u.is_authenticated and u.is_staff


@user_passes_test(_is_staff)
def admin_panel(request):
    UserModel = get_user_model()

    user_id = request.GET.get("user")
    status = request.GET.get("status")
    course_id = request.GET.get("course")
    q = request.GET.get("q", "").strip()

    users_qs = UserModel.objects.all().order_by("username")
    courses_qs = Course.objects.all().order_by("title")

    purchases_qs = (
        Purchase.objects.all()
        .select_related("user")
        .prefetch_related(
            "items",
            "items__stage",
            "items__stage__course",
            "items__bundle",
            "items__bundle__course",
        )
        .order_by("-created_at")
    )

    if user_id:
        purchases_qs = purchases_qs.filter(user_id=user_id)
    if status:
        purchases_qs = purchases_qs.filter(status=status)
    if course_id:
        try:
            cid = int(course_id)
            purchases_qs = purchases_qs.filter(
                Q(items__stage__course_id=cid) | Q(items__bundle__course_id=cid)
            )
        except ValueError:
            pass
        purchases_qs = purchases_qs.distinct()
    if q:
        purchases_qs = purchases_qs.filter(
            Q(user__username__icontains=q) | Q(user__email__icontains=q)
        )

    purchases = list(purchases_qs[:50])
    purchases = [_hydrate_purchase_display(p) for p in purchases]

    completed = []
    courses_for_completed = courses_qs
    if course_id:
        try:
            cid = int(course_id)
            courses_for_completed = courses_for_completed.filter(id=cid)
        except ValueError:
            pass

    for c in courses_for_completed:
        total_stages = c.stages.count()
        if total_stages == 0:
            continue
        rows = (
            StageProgress.objects.filter(passed=True, stage__course=c)
            .values("user_id")
            .annotate(cnt=Count("stage", distinct=True), last=Max("passed_at"))
            .filter(cnt=total_stages)
        )
        user_ids = [r["user_id"] for r in rows]
        users_map = {u.id: u for u in UserModel.objects.filter(id__in=user_ids)}
        for r in rows:
            completed.append(
                {
                    "user": users_map.get(r["user_id"]),
                    "course": c,
                    "completed_at": r["last"],
                }
            )

    completed.sort(
        key=lambda x: (x["completed_at"] or timezone.datetime.min), reverse=True
    )

    total_users = StageProgress.objects.values("user").distinct().count()
    total_courses = Course.objects.count()
    total_stages = Stage.objects.count()
    total_lessons = Lesson.objects.count()

    return render(
        request,
        "lms/admin_panel.html",
        {
            "users": users_qs,
            "courses": courses_qs,
            "selected_user_id": int(user_id) if user_id else None,
            "selected_status": status or "",
            "selected_course_id": int(course_id) if course_id else None,
            "search_q": q,
            "purchases": purchases,
            "completed": completed,
            "stage_progress": [],
            "summary": {
                "users": total_users,
                "courses": total_courses,
                "stages": total_stages,
                "lessons": total_lessons,
            },
            "users_count": total_users,
        },
    )


@user_passes_test(_is_staff)
@require_POST
def admin_update_purchase_status(request, purchase_id: int):
    new_status = request.POST.get("status")
    try:
        purchase = Purchase.objects.get(id=purchase_id)
    except Purchase.DoesNotExist:
        return HttpResponse(status=404)

    if new_status not in ("pending", "paid", "cancelled"):
        return HttpResponse("Estado inválido", status=400)

    # Si marco como pagado y todavía no estaba pagado
    if new_status == "paid" and purchase.status != "paid":
        # 👇 NO pisamos external_ref (si ya tiene TRANSFER:... o MP_..., lo dejamos)
        mark_paid_and_grant(purchase, external_ref=None)
    else:
        # Otros cambios de estado (pending / cancelled) no tocan access ni external_ref
        purchase.status = new_status
        purchase.save(update_fields=["status"])

    messages.success(request, f"Pedido #{purchase.id} actualizado a '{new_status}'.")
    return redirect(request.META.get("HTTP_REFERER", "lms:admin_panel"))


@user_passes_test(_is_staff)
@require_POST
def admin_delete_purchase(request, purchase_id: int):
    try:
        purchase = Purchase.objects.get(id=purchase_id)
    except Purchase.DoesNotExist:
        return HttpResponse(status=404)
    pid = purchase.id
    purchase.delete()
    messages.success(request, f"Pedido #{pid} eliminado.")
    return redirect(request.META.get("HTTP_REFERER", "lms:admin_panel"))


@user_passes_test(_is_staff)
@require_POST
def admin_order_status(request, purchase_id: int):
    return admin_update_purchase_status(request, purchase_id)


@user_passes_test(_is_staff)
@require_POST
def admin_order_delete(request, purchase_id: int):
    return admin_delete_purchase(request, purchase_id)


@user_passes_test(_is_staff)
def admin_user_detail(request, user_id: int):
    UserModel = get_user_model()
    the_user = get_object_or_404(UserModel, pk=user_id)

    purchases = (
        Purchase.objects.filter(user=the_user)
        .prefetch_related("items", "items__stage", "items__bundle")
        .order_by("-created_at")
    )

    progresses = (
        StageProgress.objects.filter(user=the_user)
        .select_related("stage", "stage__course")
        .order_by("-updated_at", "-passed_at")
    )

    return render(
        request,
        "lms/admin_user_detail.html",
        {
            "the_user": the_user,
            "purchases": purchases,
            "progresses": progresses,
        },
    )
