from harvest.forms import UploadForm


def test_upload_form_rejects_wrong_extension(upload_file):
    # TC-02: a .txt upload is rejected with a form error.
    form = UploadForm(files={"file": upload_file("notes.txt", "text/plain")})
    assert not form.is_valid()
    assert "file" in form.errors


def test_upload_form_rejects_oversized_file():
    # TC-03: a file over 5 MB is rejected with a form error.
    from django.core.files.uploadedfile import SimpleUploadedFile

    oversized = SimpleUploadedFile(
        "big.csv", b"ID,URL\n" + b"x" * (5 * 1024 * 1024 + 1), content_type="text/csv"
    )
    form = UploadForm(files={"file": oversized})
    assert not form.is_valid()
    assert "file" in form.errors


def test_upload_form_accepts_valid_csv(upload_file):
    form = UploadForm(files={"file": upload_file("valid.csv", "text/csv")})
    assert form.is_valid()
