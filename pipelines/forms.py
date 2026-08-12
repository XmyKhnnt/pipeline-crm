from django import forms

from .models import Pipeline, PipelineCard, PipelineStage


class PipelineForm(forms.ModelForm):
    class Meta:
        model = Pipeline
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'autofocus': True}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class PipelineStageForm(forms.ModelForm):
    class Meta:
        model = PipelineStage
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'autofocus': True})}


class PipelineCardForm(forms.ModelForm):
    """A card form limited to stages in the current pipeline."""

    class Meta:
        model = PipelineCard
        fields = [
            'title',
            'description',
            'contact_name',
            'company',
            'email',
            'phone',
            'value',
            'due_date',
            'stage',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'autofocus': True}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'value': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, pipeline: Pipeline, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.pipeline = pipeline
        self.fields['stage'].queryset = pipeline.stages.all()
