from django.contrib import admin

from .models import CompanyProfile, StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "field_of_study",
        "level",
        "language",
    )
    search_fields = (
        "user__email",
        "user__name",
        "field_of_study",
    )
    list_filter = (
        "level",
        "language",
    )


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "user",
        "phone_number",
        "website",
    )
    search_fields = (
        "company_name",
        "user__email",
    )