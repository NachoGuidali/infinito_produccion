from ..models import Stage, StageProgress, Entitlement

def has_entitlement(user, stage: Stage) -> bool:
    """¿El usuario compró esta etapa (o el curso completo que la incluye)?"""
    return Entitlement.objects.filter(user=user, stage=stage).exists()

def has_passed_previous(user, stage: Stage) -> bool:
    """¿Aprobó la etapa anterior? (para k>1)"""
    if stage.order <= 1:
        return True
    prev = Stage.objects.filter(course=stage.course, order=stage.order - 1).first()
    if not prev:
        return True
    return StageProgress.objects.filter(user=user, stage=prev, passed=True).exists()

def can_view_stage(user, stage: Stage):
    """Regla de acceso final: compra + prerrequisito aprobado."""
    if not has_entitlement(user, stage):
        return False, "No compraste esta etapa (o el curso completo)."
    if not has_passed_previous(user, stage):
        return False, "Debés aprobar la etapa anterior para acceder."
    return True, None
