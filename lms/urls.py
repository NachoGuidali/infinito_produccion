from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "lms"

urlpatterns = [
    # HOME
    path("", views.home, name="home"),

    # --- Signup (registro + confirmación por email) ---
    path("crear-cuenta/", views.signup, name="signup"),
    path("crear-cuenta/hecho/", views.signup_done, name="signup_done"),
    path("crear-cuenta/confirmar/<str:token>/", views.signup_confirm, name="signup_confirm"),
    # Alias opcional corto
    path("signup/", RedirectView.as_view(pattern_name="lms:signup", permanent=False)),

    # Catálogo (general) + atajos
    path("catalogo/", views.catalog, name="catalog"),
    path(
        "cursos/",
        RedirectView.as_view(url="/catalogo/?type=course", permanent=False),
        name="catalog_courses",
    )
    ,
    path(
        "capacitaciones/",
        RedirectView.as_view(url="/catalogo/?type=training", permanent=False),
        name="catalog_trainings",
    ),

    # Curso / Etapa / Quiz / Certificado
    path("curso/<slug:slug>/", views.course_detail, name="course_detail"),
    path("curso/<slug:slug>/certificado/", views.course_certificate, name="course_certificate"),
    path(
        "curso/<slug:course_slug>/etapa/<slug:stage_slug>/",
        views.stage_detail,
        name="stage_detail",
    ),
    path(
        "curso/<slug:course_slug>/etapa/<slug:stage_slug>/quiz/",
        views.quiz_take,
        name="quiz_take",
    ),

    # ------- Carrito -------
    path("carrito/", views.cart_view, name="cart_view"),
    path("carrito/agregar/", views.cart_add, name="cart_add"),
    path("carrito/quitar/<str:key>/", views.cart_remove, name="cart_remove"),
    path("carrito/vaciar/", views.cart_clear, name="cart_clear"),
    path("carrito/pagar/", views.cart_go_checkout, name="cart_go_checkout"),

    # Checkout + Webhook MP
    path("checkout/", views.checkout_view, name="checkout"),
    path("webhooks/pago/", views.webhook_paid, name="webhook_paid"),

    # Perfil
    path("perfil/", views.profile, name="profile"),

    # Panel admin “ligero” (ruta principal)
    path("panel-admin/", views.admin_panel, name="admin_panel"),
    path(
        "panel-admin/pedido/<int:purchase_id>/estado/",
        views.admin_order_status,
        name="admin_order_status",
    ),
    path(
        "panel-admin/pedido/<int:purchase_id>/eliminar/",
        views.admin_order_delete,
        name="admin_order_delete",
    ),
    path(
        "panel-admin/usuario/<int:user_id>/",
        views.admin_user_detail,
        name="admin_user_detail",
    ),

    # Alias corto /panel/... para no romper nada si en algún lado pusiste esa ruta
    path("panel/", RedirectView.as_view(pattern_name="lms:admin_panel", permanent=False)),
    path(
        "panel/pedido/<int:purchase_id>/estado/",
        RedirectView.as_view(pattern_name="lms:admin_order_status", permanent=False),
    ),
    path(
        "panel/pedido/<int:purchase_id>/eliminar/",
        RedirectView.as_view(pattern_name="lms:admin_order_delete", permanent=False),
    ),
    path(
        "panel/usuario/<int:user_id>/",
        RedirectView.as_view(pattern_name="lms:admin_user_detail", permanent=False),
    ),

    # Logout robusto
    path("salir/", views.logout_view, name="logout"),
]
