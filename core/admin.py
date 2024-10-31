from django.contrib import admin
from callLog.models import CallLog
from penalty.models import Penalty
from post.models import Image, Post
from team.models import Team


# Register your models here.
admin.site.register(CallLog)
admin.site.register(Penalty)
admin.site.register(Image)
admin.site.register(Post)
admin.site.register(Team)
