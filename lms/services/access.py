from ..models import Stage, StageProgress, Entitlement

def has_entitlement(user, stage: Stage) -> bool:
    """¿El usuario compró esta etapa (o el curso completo que la incluye)?"""
    return Entitlement.objects.filter(user=user, stage=stage).exists()

def has_passed(user, stage: Stage) -> bool:
    """¿Ya aprobó esta etapa?"""
    return StageProgress.objects.filter(user=user, stage=stage, passed=True).exists()

def has_passed_previous(user, stage: Stage) -> bool:
    """
    ¿Aprobó la etapa anterior?

    Se busca la etapa anterior REAL por orden (la de mayor `order` menor al de
    esta), no `order - 1`: si el curso tiene huecos o `order` repetidos, restar 1
    apunta a una etapa que no existe y el prerrequisito se saltea solo.
    """
    prev = (
        Stage.objects
        .filter(course_id=stage.course_id, order__lt=stage.order)
        .order_by("-order", "-id")
        .first()
    )
    if not prev:
        return True
    return has_passed(user, prev)

def can_view_stage(user, stage: Stage):
    """Regla de acceso final: compra + prerrequisito aprobado."""
    if not has_entitlement(user, stage):
        return False, "No compraste esta etapa (o el curso completo)."

    # Una etapa ya aprobada queda accesible para siempre: el alumno tiene que
    # poder volver a repasar el material. Además evita que reordenar o insertar
    # etapas en el wizard le bloquee retroactivamente lo que ya cursó (la etapa
    # nueva pasa a ser "la anterior" de una que ya tenía aprobada).
    if has_passed(user, stage):
        return True, None

    if not has_passed_previous(user, stage):
        return False, "Debés aprobar la etapa anterior para acceder."
    return True, None
