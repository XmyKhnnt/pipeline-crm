from django.contrib import admin

from .models import Pipeline, PipelineCard, PipelineStage


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'description', 'owner__username')
    ordering = ('-updated_at',)


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'pipeline', 'position', 'updated_at')
    list_filter = ('pipeline',)
    search_fields = ('name', 'pipeline__name')
    ordering = ('pipeline', 'position')


@admin.register(PipelineCard)
class PipelineCardAdmin(admin.ModelAdmin):
    list_display = ('title', 'pipeline', 'stage', 'company', 'value', 'due_date')
    list_filter = ('pipeline', 'stage', 'due_date')
    search_fields = ('title', 'company', 'contact_name', 'email')
    ordering = ('pipeline', 'stage', 'position')

# Register your models here.
