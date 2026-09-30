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
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "club", "role")
    list_filter = ("club", "role")
    search_fields = ("user__username", "user__email", "club__name")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("club", "created_by", "created_at", "expires_at", "used_by", "used_at")
    list_filter = ("club",)
    readonly_fields = ("token",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "club", "is_own", "in_group", "location")
    list_filter = ("club", "is_own", "in_group")
    search_fields = ("name", "location")


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ("call", "text")
    list_filter = ("call__match__club",)
    search_fields = ("text",)


@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    list_display = ("player", "reason", "call")
    list_filter = ("player__club",)
    search_fields = ("player__name", "player__last_name", "reason")


admin.site.site_header = "Zyra"
admin.site.site_title = "Zyra"
admin.site.index_title = "Administración"


def _superuser_only(request):
    # El Django admin queda como herramienta de emergencia del dueño de la plataforma;
    # el día a día va por el back-office (/backoffice/).
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = _superuser_only
