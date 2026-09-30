from django.contrib import admin
from callLog.models import CallLog
from penalty.models import Penalty
from team.models import Team
from .models import Club, Invitation, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "club", "role")
    list_filter = ("club", "role")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("club", "created_by", "created_at", "expires_at", "used_by", "used_at")
    list_filter = ("club",)
    readonly_fields = ("token",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "club", "is_own", "in_group")
    list_filter = ("club",)


admin.site.site_header = "Zyra"
admin.site.site_title = "Zyra"
admin.site.index_title = "Administración"

# Register your models here.
admin.site.register(CallLog)
admin.site.register(Penalty)
