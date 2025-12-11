from django.contrib import admin
from .models import (
    Course, Stage, Lesson, Quiz, Question, Choice,
    Enrollment, StageProgress, QuizAttempt,
    Bundle, Purchase, PurchaseItem, Entitlement
)

# -------------------------
# Courses
# -------------------------
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "slug", "is_active")
    list_filter  = ("kind",)
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    # mostramos y ordenamos los campos importantes en el formulario
    fields = ("title", "slug", "description", "image_url", "is_active", "kind")

# -------------------------
# Stages
# -------------------------
@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    # Si tu Stage NO tiene price_ars, quitá "price_ars" de list_display.
    list_display = ("course", "title", "order", "price_ars")
    list_filter = ("course",)
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}

# -------------------------
# Lessons / Quiz / QA
# -------------------------
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("stage", "title", "order")
    list_filter = ("stage",)
    search_fields = ("title",)

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("stage", "passing_score", "max_attempts")

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("quiz", "text")
    search_fields = ("text",)

@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ("question", "text", "is_correct")
    list_filter = ("is_correct",)

# -------------------------
# Enrollment / Progress / Attempts
# -------------------------
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "started_at")
    list_filter = ("course",)

@admin.register(StageProgress)
class StageProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "stage", "passed", "score", "passed_at")
    list_filter = ("passed", "stage")

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "quiz", "score", "passed", "created_at")
    list_filter = ("passed",)

# -------------------------
# Bundles / Purchases / Entitlements
# -------------------------
@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("course", "title", "price_ars")
    filter_horizontal = ("stages",)

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_ars", "external_ref", "created_at")
    list_filter = ("status",)
    inlines = [PurchaseItemInline]

@admin.register(Entitlement)
class EntitlementAdmin(admin.ModelAdmin):
    list_display = ("user", "stage", "source", "created_at")
    list_filter = ("source",)
