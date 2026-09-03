from django import forms

from .models import CompanyProfile, StudentProfile


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = (
            "field_of_study",
            "level",
            "skills",
            "language",
            "cv",
        )


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = (
            "company_name",
            "description",
            "phone_number",
            "address",
            "website",
            "logo",
        )