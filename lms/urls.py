from django.urls import path
from django.views.generic import RedirectView
from . import views
from . import views_store

app_name = "lms"

urlpatterns = [
    # HOME
    path("", views.home, name="home"),

    # --- Signup (registro + confirmación por email) ---
    path("crear-cuenta/", views.signup, name="signup"),
    path("crear-cuenta/hecho/", views.signup_done, name="signup_done"),
    path("crear-cuenta/reenviar/", views.resend_activation, name="resend_activation"),
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
    path("mis-pedidos/", views_store.store_my_orders, name="store_my_orders"),
    path("mis-pedidos/<int:order_id>/pagar/", views_store.store_order_pay, name="store_order_pay"),

    # Panel admin "ligero" (ruta principal)
    path("panel-admin/", views.admin_panel, name="admin_panel"),

    # Wizard de cursos
    path("panel-admin/cursos/", views.course_wizard, name="course_wizard"),
    path("panel-admin/cursos/nuevo/guardar/", views.course_wizard_save, name="course_wizard_save"),
    path("panel-admin/cursos/<int:course_id>/", views.course_wizard, name="course_wizard_edit"),
    path("panel-admin/cursos/<int:course_id>/guardar/", views.course_wizard_save, name="course_wizard_save_edit"),
    path("panel-admin/cursos/<int:course_id>/eliminar/", views.course_wizard_delete, name="course_wizard_delete"),

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

    # ─── TIENDA DE PRODUCTOS ──────────────────────────────────────
    path("tienda/", views_store.store, name="store"),
    path("tienda/producto/<slug:slug>/", views_store.store_product_detail, name="store_product_detail"),

    # Carrito tienda
    path("tienda/carrito/", views_store.store_cart, name="store_cart"),
    path("tienda/carrito/agregar/<int:product_id>/", views_store.store_cart_add, name="store_cart_add"),
    path("tienda/carrito/quitar/<str:key>/", views_store.store_cart_remove, name="store_cart_remove"),
    path("tienda/carrito/actualizar/<str:key>/", views_store.store_cart_update, name="store_cart_update"),
    path("tienda/envio/calcular/", views_store.store_shipping_calc, name="store_shipping_calc"),
    path("tienda/descuento/validar/", views_store.store_discount_check, name="store_discount_check"),

    # Checkout tienda
    path("tienda/checkout/", views_store.store_checkout, name="store_checkout"),
    path("tienda/pago-retorno/", views_store.store_payment_return, name="store_payment_return"),
    path("tienda/pedido/<int:order_id>/confirmado/", views_store.store_order_success, name="store_order_success"),

    # ─── ADMIN TIENDA ─────────────────────────────────────────────
    path("panel-admin/tienda/", views_store.store_admin, name="store_admin"),

    # Productos admin
    path("panel-admin/tienda/producto/nuevo/", views_store.store_admin_product_create, name="store_admin_product_create"),
    path("panel-admin/tienda/producto/<int:product_id>/editar/", views_store.store_admin_product_edit, name="store_admin_product_edit"),
    path("panel-admin/tienda/producto/<int:product_id>/eliminar/", views_store.store_admin_product_delete, name="store_admin_product_delete"),
    path("panel-admin/tienda/productos/importar/", views_store.store_admin_product_import, name="store_admin_product_import"),
    path("panel-admin/tienda/productos/plantilla/", views_store.store_admin_product_import_template, name="store_admin_product_import_template"),

    # Categorías admin
    path("panel-admin/tienda/categoria/guardar/", views_store.store_admin_category_save, name="store_admin_category_save"),
    path("panel-admin/tienda/categoria/<int:cat_id>/eliminar/", views_store.store_admin_category_delete, name="store_admin_category_delete"),

    # Códigos de descuento admin
    path("panel-admin/tienda/descuento/guardar/", views_store.store_admin_discount_save, name="store_admin_discount_save"),
    path("panel-admin/tienda/descuento/<int:code_id>/estado/", views_store.store_admin_discount_toggle, name="store_admin_discount_toggle"),
    path("panel-admin/tienda/descuento/<int:code_id>/eliminar/", views_store.store_admin_discount_delete, name="store_admin_discount_delete"),

    # Pedidos admin
    path("panel-admin/tienda/pedido/<int:order_id>/", views_store.store_admin_order_detail, name="store_admin_order_detail"),
    path("panel-admin/tienda/pedido/<int:order_id>/actualizar/", views_store.store_admin_order_update, name="store_admin_order_update"),
    path("panel-admin/tienda/pedido/<int:order_id>/eliminar/", views_store.store_admin_order_delete, name="store_admin_order_delete"),
    path("panel-admin/tienda/pedidos/nuevos/", views_store.store_admin_new_orders, name="store_admin_new_orders"),

    # Envíos admin
    path("panel-admin/tienda/envios/guardar/", views_store.store_admin_shipping_save, name="store_admin_shipping_save"),
    path("panel-admin/tienda/zona/guardar/", views_store.store_admin_zone_save, name="store_admin_zone_save"),
    path("panel-admin/tienda/zona/<int:zone_id>/eliminar/", views_store.store_admin_zone_delete, name="store_admin_zone_delete"),
    path("panel-admin/tienda/zonas/importar/", views_store.store_admin_zone_import, name="store_admin_zone_import"),
    path("panel-admin/tienda/zonas/plantilla/", views_store.store_admin_zone_import_template, name="store_admin_zone_import_template"),

    # Logout robusto
    path("salir/", views.logout_view, name="logout"),
]
