from django import forms

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = (".csv", ".xlsx")


class UploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        name = uploaded.name.lower()
        if not name.endswith(ALLOWED_EXTENSIONS):
            raise forms.ValidationError("Only .csv and .xlsx files are supported.")
        if uploaded.size > MAX_UPLOAD_SIZE_BYTES:
            raise forms.ValidationError("File must be 5 MB or smaller.")
        return uploaded
