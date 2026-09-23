import pytest
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.views.defaults import server_error


@pytest.mark.django_db
def test_api_unhandled_exception_returns_internal_error_and_never_leaks_it(monkeypatch, client):
    # TC-66
    def _boom():
        raise RuntimeError("boom - should never reach the client")

    monkeypatch.setattr("api.views.get_vector_store", _boom)

    response = client.post(
        reverse("api:search"),
        data='{"query": "who is the CEO?"}',
        content_type="application/json",
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal error."}
    body = response.content.decode()
    assert "boom" not in body
    assert "RuntimeError" not in body
    assert "Traceback" not in body


@override_settings(DEBUG=False)
def test_html_404_renders_friendly_page_not_a_traceback(client):
    # TC-67
    response = client.get("/this-page-does-not-exist/")

    assert response.status_code == 404
    content = response.content.decode()
    assert "Page not found" in content
    assert "Traceback" not in content


def test_html_500_template_renders_friendly_page_not_a_traceback():
    # TC-68
    # Django's server_error view (used for the real 500 path) renders
    # templates/500.html with a bare context and no request-context
    # dependency, by design -- called directly here rather than triggering a
    # genuine unhandled view exception end-to-end.
    request = RequestFactory().get("/")

    response = server_error(request)

    assert response.status_code == 500
    content = response.content.decode()
    assert "Something went wrong" in content
    assert "Traceback" not in content
