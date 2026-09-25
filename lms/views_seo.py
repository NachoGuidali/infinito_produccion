"""
lms/views_seo.py
robots.txt y sitemap.xml. Se generan desde la base para que los cursos y
productos nuevos aparezcan solos, sin tener que editar nada a mano.
"""
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from .models import Course, Product

# Rutas privadas o sin valor para buscadores.
_BLOQUEADAS = [
    "/admin/",
    "/panel-admin/",
    "/panel/",
    "/carrito/",
    "/checkout/",
    "/perfil/",
    "/mis-pedidos/",
    "/tienda/carrito/",
    "/tienda/checkout/",
    "/tienda/pago-retorno/",
    "/webhooks/",
    "/login/",
    "/logout/",
    "/crear-cuenta/",
    "/password_reset/",
    "/reset/",
]


@require_GET
def robots_txt(request):
    base = f"{request.scheme}://{request.get_host()}"
    lineas = ["User-agent: *"]
    lineas += [f"Disallow: {ruta}" for ruta in _BLOQUEADAS]
    lineas += ["Allow: /", "", f"Sitemap: {base}/sitemap.xml", ""]
    return HttpResponse("\n".join(lineas), content_type="text/plain; charset=utf-8")


def _url(base, ruta, prioridad, frecuencia, lastmod=None):
    partes = [f"    <loc>{base}{ruta}</loc>"]
    if lastmod:
        partes.append(f"    <lastmod>{lastmod:%Y-%m-%d}</lastmod>")
    partes.append(f"    <changefreq>{frecuencia}</changefreq>")
    partes.append(f"    <priority>{prioridad}</priority>")
    return "  <url>\n" + "\n".join(partes) + "\n  </url>"


@require_GET
def sitemap_xml(request):
    base = f"{request.scheme}://{request.get_host()}"
    urls = [
        _url(base, "/", "1.0", "weekly"),
        _url(base, reverse("lms:catalog"), "0.9", "weekly"),
        _url(base, "/cursos/", "0.9", "weekly"),
        _url(base, "/capacitaciones/", "0.8", "weekly"),
        _url(base, reverse("lms:store"), "0.7", "weekly"),
    ]

    for course in Course.objects.filter(is_active=True).order_by("id"):
        urls.append(_url(
            base,
            reverse("lms:course_detail", args=[course.slug]),
            "0.8",
            "monthly",
        ))

    for product in Product.objects.filter(is_active=True).order_by("id"):
        urls.append(_url(
            base,
            reverse("lms:store_product_detail", args=[product.slug]),
            "0.6",
            "monthly",
            getattr(product, "updated_at", None),
        ))

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")
