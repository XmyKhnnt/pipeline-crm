import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Max
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PipelineCardForm, PipelineForm, PipelineStageForm
from .models import Pipeline, PipelineCard, PipelineStage


DEFAULT_STAGES = ('New', 'In Progress', 'Won', 'Lost')


def _owned_pipeline(request: HttpRequest, pipeline_id: int) -> Pipeline:
    return get_object_or_404(Pipeline, pk=pipeline_id, owner=request.user)


def _touch_pipeline(pipeline: Pipeline) -> None:
    Pipeline.objects.filter(pk=pipeline.pk).update(updated_at=timezone.now())


def _resequence_stages(pipeline: Pipeline, stage_ids: list[int]) -> None:
    """Write a complete, collision-free stage order for one pipeline."""
    stages = pipeline.stages.all()
    maximum = stages.aggregate(maximum=Max('position'))['maximum'] or 0
    stages.update(position=F('position') + maximum + len(stage_ids) + 1)
    for position, stage_id in enumerate(stage_ids, start=1):
        stages.filter(pk=stage_id).update(position=position)


def _resequence_cards(stage_id: int, card_ids: list[int]) -> None:
    """Write a complete, collision-free card order for one stage."""
    cards = PipelineCard.objects.filter(stage_id=stage_id)
    maximum = cards.aggregate(maximum=Max('position'))['maximum'] or 0
    cards.update(position=F('position') + maximum + len(card_ids) + 1)
    for position, card_id in enumerate(card_ids, start=1):
        cards.filter(pk=card_id).update(position=position)


def _move_card(card: PipelineCard, destination: PipelineStage, position: int) -> None:
    """Move a card and deterministically resequence every affected column."""
    source_id = card.stage_id
    source_ids = list(
        PipelineCard.objects.select_for_update()
        .filter(stage_id=source_id)
        .order_by('position', 'id')
        .values_list('id', flat=True)
    )
    if source_id == destination.pk:
        destination_ids = source_ids
    else:
        destination_ids = list(
            PipelineCard.objects.select_for_update()
            .filter(stage=destination)
            .order_by('position', 'id')
            .values_list('id', flat=True)
        )

    source_ids.remove(card.pk)
    destination_ids = [card_id for card_id in destination_ids if card_id != card.pk]
    destination_ids.insert(position, card.pk)

    maximum = max(
        PipelineCard.objects.filter(stage_id__in=[source_id, destination.pk]).aggregate(
            maximum=Max('position')
        )['maximum']
        or 0,
        0,
    )
    PipelineCard.objects.filter(pk=card.pk).update(
        stage=destination,
        position=maximum + len(source_ids) + len(destination_ids) + 1,
        updated_at=timezone.now(),
    )
    if source_id != destination.pk:
        _resequence_cards(source_id, source_ids)
    _resequence_cards(destination.pk, destination_ids)


@login_required
def pipeline_list(request: HttpRequest):
    pipelines = (
        Pipeline.objects.filter(owner=request.user)
        .annotate(stage_total=Count('stages', distinct=True), card_total=Count('cards', distinct=True))
        .order_by('-updated_at', 'name')
    )
    return render(request, 'pipelines/pipeline_list.html', {'pipelines': pipelines})


@login_required
def pipeline_create(request: HttpRequest):
    if request.method == 'POST':
        form = PipelineForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                pipeline = form.save(commit=False)
                pipeline.owner = request.user
                pipeline.save()
                PipelineStage.objects.bulk_create(
                    [
                        PipelineStage(pipeline=pipeline, name=name, position=position)
                        for position, name in enumerate(DEFAULT_STAGES, start=1)
                    ]
                )
            messages.success(request, 'Pipeline created.')
            return redirect('pipelines:detail', pipeline_id=pipeline.pk)
    else:
        form = PipelineForm()
    return render(
        request,
        'pipelines/pipeline_form.html',
        {'form': form, 'title': 'Create Pipeline', 'submit_label': 'Create Pipeline'},
    )


@login_required
def pipeline_detail(request: HttpRequest, pipeline_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    stages = pipeline.stages.prefetch_related('cards').all()
    return render(request, 'pipelines/pipeline_board.html', {'pipeline': pipeline, 'stages': stages})


@login_required
def pipeline_edit(request: HttpRequest, pipeline_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    if request.method == 'POST':
        form = PipelineForm(request.POST, instance=pipeline)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pipeline updated.')
            return redirect('pipelines:detail', pipeline_id=pipeline.pk)
    else:
        form = PipelineForm(instance=pipeline)
    return render(
        request,
        'pipelines/pipeline_form.html',
        {
            'form': form,
            'title': 'Edit Pipeline',
            'submit_label': 'Save changes',
            'pipeline': pipeline,
        },
    )


@login_required
def pipeline_delete(request: HttpRequest, pipeline_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    if request.method == 'POST':
        with transaction.atomic():
            pipeline.cards.all().delete()
            pipeline.stages.all().delete()
            pipeline.delete()
        messages.success(request, 'Pipeline deleted.')
        return redirect('pipelines:list')
    return render(request, 'pipelines/pipeline_confirm_delete.html', {'pipeline': pipeline})


@login_required
def stage_create(request: HttpRequest, pipeline_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    if request.method == 'POST':
        form = PipelineStageForm(request.POST)
        if form.is_valid():
            position = (pipeline.stages.aggregate(maximum=Max('position'))['maximum'] or 0) + 1
            stage = form.save(commit=False)
            stage.pipeline = pipeline
            stage.position = position
            stage.save()
            _touch_pipeline(pipeline)
            messages.success(request, 'Stage added.')
            return redirect('pipelines:detail', pipeline_id=pipeline.pk)
    else:
        form = PipelineStageForm()
    return render(
        request,
        'pipelines/stage_form.html',
        {'form': form, 'pipeline': pipeline, 'title': 'Add Stage', 'submit_label': 'Add Stage'},
    )


@login_required
def stage_edit(request: HttpRequest, pipeline_id: int, stage_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    stage = get_object_or_404(pipeline.stages, pk=stage_id)
    if request.method == 'POST':
        form = PipelineStageForm(request.POST, instance=stage)
        if form.is_valid():
            form.save()
            _touch_pipeline(pipeline)
            messages.success(request, 'Stage renamed.')
            return redirect('pipelines:detail', pipeline_id=pipeline.pk)
    else:
        form = PipelineStageForm(instance=stage)
    return render(
        request,
        'pipelines/stage_form.html',
        {
            'form': form,
            'pipeline': pipeline,
            'stage': stage,
            'title': 'Rename Stage',
            'submit_label': 'Save changes',
        },
    )


@login_required
@require_POST
def stage_delete(request: HttpRequest, pipeline_id: int, stage_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    stage = get_object_or_404(pipeline.stages, pk=stage_id)
    card_count = stage.cards.count()
    if card_count:
        messages.error(
            request,
            f'This stage contains {card_count} card{'s' if card_count != 1 else ''}. '
            'Move those cards to another stage before deleting this stage.',
        )
        return redirect('pipelines:detail', pipeline_id=pipeline.pk)

    with transaction.atomic():
        try:
            stage.delete()
        except ProtectedError:
            messages.error(request, 'Move cards to another stage before deleting this stage.')
        else:
            stage_ids = list(pipeline.stages.values_list('id', flat=True))
            _resequence_stages(pipeline, stage_ids)
            _touch_pipeline(pipeline)
            messages.success(request, 'Stage deleted.')
    return redirect('pipelines:detail', pipeline_id=pipeline.pk)


@login_required
@require_POST
def stage_reorder(request: HttpRequest, pipeline_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    try:
        stage_ids = json.loads(request.body).get('stage_ids')
        stage_ids = [int(stage_id) for stage_id in stage_ids]
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return HttpResponseBadRequest('A valid stage order is required.')

    current_ids = list(pipeline.stages.values_list('id', flat=True))
    if len(stage_ids) != len(current_ids) or set(stage_ids) != set(current_ids):
        return HttpResponseBadRequest('The supplied stages do not match this pipeline.')

    with transaction.atomic():
        _resequence_stages(pipeline, stage_ids)
        _touch_pipeline(pipeline)
    return JsonResponse({'ok': True})


@login_required
def card_create(request: HttpRequest, pipeline_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    initial = {}
    if request.method == 'GET' and request.GET.get('stage'):
        initial['stage'] = get_object_or_404(pipeline.stages, pk=request.GET['stage'])

    if request.method == 'POST':
        form = PipelineCardForm(request.POST, pipeline=pipeline)
        if form.is_valid():
            with transaction.atomic():
                card = form.save(commit=False)
                card.created_by = request.user
                card.position = (
                    PipelineCard.objects.filter(stage=card.stage).aggregate(maximum=Max('position'))[
                        'maximum'
                    ]
                    or 0
                ) + 1
                card.save()
                _touch_pipeline(pipeline)
            messages.success(request, 'Card added.')
            return redirect('pipelines:detail', pipeline_id=pipeline.pk)
    else:
        form = PipelineCardForm(pipeline=pipeline, initial=initial)
    return render(
        request,
        'pipelines/card_form.html',
        {'form': form, 'pipeline': pipeline, 'title': 'Add Card', 'submit_label': 'Add Card'},
    )


@login_required
def card_edit(request: HttpRequest, pipeline_id: int, card_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    card = get_object_or_404(pipeline.cards, pk=card_id)
    if request.method == 'POST':
        old_stage_id = card.stage_id
        form = PipelineCardForm(request.POST, instance=card, pipeline=pipeline)
        if form.is_valid():
            destination = form.cleaned_data['stage']
            with transaction.atomic():
                if destination.pk == old_stage_id:
                    form.save()
                else:
                    card.stage_id = old_stage_id
                    card.save()
                    _move_card(card, destination, destination.cards.exclude(pk=card.pk).count())
                _touch_pipeline(pipeline)
            messages.success(request, 'Card updated.')
            return redirect('pipelines:detail', pipeline_id=pipeline.pk)
    else:
        form = PipelineCardForm(instance=card, pipeline=pipeline)
    return render(
        request,
        'pipelines/card_form.html',
        {
            'form': form,
            'pipeline': pipeline,
            'card': card,
            'title': 'Edit Card',
            'submit_label': 'Save changes',
        },
    )


@login_required
@require_POST
def card_delete(request: HttpRequest, pipeline_id: int, card_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    card = get_object_or_404(pipeline.cards, pk=card_id)
    stage_id = card.stage_id
    with transaction.atomic():
        card.delete()
        card_ids = list(
            PipelineCard.objects.filter(stage_id=stage_id)
            .order_by('position', 'id')
            .values_list('id', flat=True)
        )
        _resequence_cards(stage_id, card_ids)
        _touch_pipeline(pipeline)
    messages.success(request, 'Card deleted.')
    return redirect('pipelines:detail', pipeline_id=pipeline.pk)


@login_required
@require_POST
def card_move(request: HttpRequest, pipeline_id: int, card_id: int):
    pipeline = _owned_pipeline(request, pipeline_id)
    card = get_object_or_404(pipeline.cards, pk=card_id)
    try:
        payload = json.loads(request.body)
        supplied_card_id = int(payload['card_id'])
        destination_stage_id = int(payload['destination_stage_id'])
        position = int(payload['position'])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return HttpResponseBadRequest('A valid card move is required.')

    if supplied_card_id != card.pk:
        return HttpResponseBadRequest('The supplied card does not match this URL.')
    destination = get_object_or_404(pipeline.stages, pk=destination_stage_id)
    destination_count = destination.cards.exclude(pk=card.pk).count()
    if position < 0 or position > destination_count:
        return HttpResponseBadRequest('The supplied position is invalid.')

    with transaction.atomic():
        _move_card(card, destination, position)
        _touch_pipeline(pipeline)
    return JsonResponse({'ok': True})

# Create your views here.
