from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404

import mercadopago

from ..models import (
    Purchase,
    PurchaseItem,
    Bundle,
    Stage,
    Entitlement,
    Enrollment,
)


def create_checkout(user, items):
    """
    Crea una Purchase 'pending' con sus PurchaseItems.

    items = [
      {"type": "stage", "id": <stage_id>, "price_ars": Decimal|None},
      {"type": "bundle", "id": <bundle_id>, "price_ars": Decimal|None},
    ]
    """
    with transaction.atomic():
        p = Purchase.objects.create(
            user=user,
            status="pending",
            total_ars=Decimal("0"),
        )
        total = Decimal("0")

        for it in items:
            if it["type"] == "stage":
                stage = get_object_or_404(Stage, id=it["id"])
                price = Decimal(str(it.get("price_ars") or stage.price_ars))
                PurchaseItem.objects.create(
                    purchase=p,
                    type="stage",
                    stage=stage,
                    price_ars=price,
                )
                total += price

            elif it["type"] == "bundle":
                bundle = get_object_or_404(Bundle, id=it["id"])
                price = Decimal(str(it.get("price_ars") or bundle.price_ars))
                PurchaseItem.objects.create(
                    purchase=p,
                    type="bundle",
                    bundle=bundle,
                    price_ars=price,
                )
                total += price

            else:
                raise ValueError("Tipo de ítem inválido (usa 'stage' o 'bundle').")

        p.total_ars = total
        p.save()

    return p


def mark_paid_and_grant(purchase: Purchase, external_ref: str | None = None):
    """
    Marca la compra como pagada y otorga:
      - Enrollment por cada curso involucrado
      - Entitlements por cada etapa comprada (directa) o incluida en el bundle
    """
    if purchase.status == "paid":
        return  # idempotente

    purchase.status = "paid"
    if external_ref:
        purchase.external_ref = external_ref
    purchase.save()

    # 1) Enrollment por curso
    course_ids = set()
    for item in purchase.items.all():
        if item.type == "stage" and item.stage:
            course_ids.add(item.stage.course_id)
        elif item.type == "bundle" and item.bundle:
            course_ids.add(item.bundle.course_id)

    for cid in course_ids:
        Enrollment.objects.get_or_create(user=purchase.user, course_id=cid)

    # 2) Entitlements por etapa
    for item in purchase.items.all():
        if item.type == "stage" and item.stage:
            Entitlement.objects.get_or_create(
                user=purchase.user,
                stage=item.stage,
                defaults={"source": "stage"},
            )

        elif item.type == "bundle" and item.bundle:
            for st in item.bundle.stages.all():
                Entitlement.objects.get_or_create(
                    user=purchase.user,
                    stage=st,
                    defaults={"source": "bundle"},
                )


# ============================================================
# Mercado Pago: creación de preferencia para una Purchase
# ============================================================

def create_mp_preference_for_purchase(purchase: Purchase):
    """
    Crea una preferencia de Mercado Pago para la Purchase indicada y
    devuelve (preference_id, init_point).

    - Usa MP_ACCESS_TOKEN de settings / .env
    - external_reference = purchase.id  (clave para el webhook)
    - notification_url   = MP_WEBHOOK_URL
    - back_urls          = MP_SUCCESS_URL (success/failure/pending)
    """
    access_token = getattr(settings, "MP_ACCESS_TOKEN", "")
    if not access_token:
        # Si no hay token, devolvemos None y el checkout mostrará mensaje
        return None, None

    sdk = mercadopago.SDK(access_token)

    items = []
    for it in purchase.items.all():
        if it.stage:
            title = f"Etapa: {it.stage.title} ({it.stage.course.title})"
        elif it.bundle:
            title = f"Curso completo: {it.bundle.course.title}"
        else:
            title = "Infinito Capacitaciones"

        items.append(
            {
                "title": title,
                "quantity": 1,
                "unit_price": float(it.price_ars or 0),
                "currency_id": "ARS",
            }
        )

    preference_data = {
        "items": items,
        # esto nos permite saber QUÉ purchase aprobar en el webhook
        "external_reference": str(purchase.id),
        "notification_url": getattr(settings, "MP_WEBHOOK_URL", "") or "",
        "back_urls": {
            "success": getattr(settings, "MP_SUCCESS_URL", "") or "",
            "failure": getattr(settings, "MP_SUCCESS_URL", "") or "",
            "pending": getattr(settings, "MP_SUCCESS_URL", "") or "",
        },
        "auto_return": "approved",
    }

    result = sdk.preference().create(preference_data)
    pref = result.get("response", {}) if isinstance(result, dict) else {}
    pref_id = pref.get("id")
    init_point = pref.get("init_point") or pref.get("sandbox_init_point")

    return pref_id, init_point
