from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Pipeline(models.Model):
    """A user-owned Kanban board."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pipelines',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', 'name']

    def __str__(self) -> str:
        return self.name


class PipelineStage(models.Model):
    """A positioned column in a pipeline."""

    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        related_name='stages',
    )
    name = models.CharField(max_length=80)
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['pipeline', 'position'], name='unique_stage_position_per_pipeline'
            ),
        ]

    def __str__(self) -> str:
        return f'{self.pipeline}: {self.name}'


class PipelineCard(models.Model):
    """A compact CRM item shown on a pipeline board."""

    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        related_name='cards',
    )
    stage = models.ForeignKey(
        PipelineStage,
        on_delete=models.PROTECT,
        related_name='cards',
    )
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField()
    contact_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=160, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_pipeline_cards',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['stage', 'position'], name='unique_card_position_per_stage'
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.stage_id and self.pipeline_id and self.stage.pipeline_id != self.pipeline_id:
            raise ValidationError({'stage': 'The selected stage belongs to another pipeline.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title

# Create your models here.
