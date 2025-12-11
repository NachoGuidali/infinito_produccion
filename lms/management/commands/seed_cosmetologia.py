from django.core.management.base import BaseCommand
from django.utils.text import slugify
from lms.models import Course, Stage, Lesson, Quiz, Question, Choice, Bundle
from lms.utils import youtube_to_embed

class Command(BaseCommand):
    help = "Carga el curso 'Cosmetología y cosmiatría' con 5 etapas. Etapa 1 completa + quiz; Etapa 2 con placeholder."

    def handle(self, *args, **kwargs):
        # Curso
        title = "Cosmetología y cosmiatría"
        course, _ = Course.objects.get_or_create(
            title=title,
            slug=slugify(title),
            defaults={"description": ""},
        )

        # Precios
        precio_etapa = 30000
        bundle_price = int(5 * precio_etapa * 0.9)   # auto: 10% desc

        # Crear 5 etapas (Etapa 1 completa; Etapa 2 placeholder; 3..5 vacías)
        etapas_data = [
            {"order": 1, "slug": "etapa-1", "title": "Etapa 1", "pdf": ""},
            {"order": 2, "slug": "etapa-2", "title": "Etapa 2", "pdf": ""},
            {"order": 3, "slug": "etapa-3", "title": "Etapa 3", "pdf": ""},
            {"order": 4, "slug": "etapa-4", "title": "Etapa 4", "pdf": ""},
            {"order": 5, "slug": "etapa-5", "title": "Etapa 5", "pdf": ""},
        ]

        stages = []
        for e in etapas_data:
            st, _ = Stage.objects.get_or_create(
                course=course,
                order=e["order"],
                slug=e["slug"],
                defaults={
                    "title": e["title"],
                    "price_ars": precio_etapa,
                    "pdf_url": e["pdf"],
                },
            )
            stages.append(st)

        # Lecciones Etapa 1 (usando tus links; convierto a embed)
        etapa1 = stages[0]
        lessons = [
            ("Introduccion", "https://youtu.be/drM7njNNVkE?si=xdzm639IVy7-Ibno", ""),
            ("MODULO 1, 2 y 3", "", ""),
            ("\"MODULO 1\" en YouTube", "https://youtu.be/RcgBpVSqXPw?si=o6Frojgo1oYewubh", ""),
            ("“MÓDULO 2” en YouTube", "https://youtu.be/kg0fynEo7s0?si=rMgAhNc8aSa6xRn6", ""),
            ("“MÓDULO 3” en YouTube", "https://youtu.be/DNtTGN45fHY?si=v67YeMEqpf9K_134", ""),
            ("PARTE 1: LIMPIEZA DE CUTIS. PREPARACIÓN PREVIA", "https://www.youtube.com/watch?v=CHnx6GWdKi4", ""),
            ("PARTE 2: LIMPIEZA DE CUTIS", "https://www.youtube.com/watch?v=8neGNyqFtPM", ""),
            ("PARTE 3: LIMPIEZA DE CUTIS", "https://www.youtube.com/watch?v=43FcdZL1zyA", ""),
            ("PARTE 4: LIMPIEZA DE CUTIS", "https://www.youtube.com/watch?v=PPwq3o_MEgc", ""),
        ]
        order = 1
        for title, yurl, pdf in lessons:
            Lesson.objects.get_or_create(
                stage=etapa1,
                order=order,
                defaults={
                    "title": title,
                    "youtube_url": youtube_to_embed(yurl) if yurl else yurl,
                    "pdf_url": pdf or "",
                },
            )
            order += 1

        # Quiz Etapa 1 (80%, intentos ilimitados)
        quiz1, _ = Quiz.objects.get_or_create(
            stage=etapa1,
            defaults={"passing_score": 80, "max_attempts": 0},
        )
        # Pregunta 1
        q1, _ = Question.objects.get_or_create(
            quiz=quiz1,
            text="¿Cuál de las siguientes afirmaciones sobre las emulsiones es correcta?",
        )
        Choice.objects.get_or_create(question=q1, text="Están formadas solo por fase acuosa.", is_correct=False)
        Choice.objects.get_or_create(question=q1, text="Son soluciones transparentes y sin color.", is_correct=False)
        Choice.objects.get_or_create(question=q1, text="Son mezclas de una fase acuosa y una lipídica.", is_correct=True)
        Choice.objects.get_or_create(question=q1, text="Solo se utilizan en tratamientos corporales.", is_correct=False)

        # Pregunta 2
        q2, _ = Question.objects.get_or_create(
            quiz=quiz1,
            text="¿Qué tipo de emulsión tiene agua como fase interna?",
        )
        Choice.objects.get_or_create(question=q2, text="O/W", is_correct=False)
        Choice.objects.get_or_create(question=q2, text="W/O", is_correct=True)
        Choice.objects.get_or_create(question=q2, text="H/W", is_correct=False)
        Choice.objects.get_or_create(question=q2, text="W/A", is_correct=False)

        # Etapa 2 placeholder (1 clase vacía editable desde admin)
        etapa2 = stages[1]
        Lesson.objects.get_or_create(
            stage=etapa2,
            order=1,
            defaults={
                "title": "Prueba",
                "youtube_url": "",
                "pdf_url": "",
            },
        )

        # Bundle (curso completo)
        bundle, _ = Bundle.objects.get_or_create(
            course=course,
            title="Curso Completo",
            defaults={"price_ars": bundle_price},
        )
        bundle.stages.set(stages)

        self.stdout.write(self.style.SUCCESS("Curso Cosmetología cargado."))
        self.stdout.write(self.style.SUCCESS(f"Bundle auto: ${bundle_price} (5 x {precio_etapa} con 10% desc.)"))
