from django.urls import path

from . import views

app_name = 'pipelines'

urlpatterns = [
    path('', views.pipeline_list, name='list'),
    path('pipelines/', views.pipeline_list, name='list-alias'),
    path('pipelines/create/', views.pipeline_create, name='create'),
    path('pipelines/<int:pipeline_id>/', views.pipeline_detail, name='detail'),
    path('pipelines/<int:pipeline_id>/edit/', views.pipeline_edit, name='edit'),
    path('pipelines/<int:pipeline_id>/delete/', views.pipeline_delete, name='delete'),
    path('pipelines/<int:pipeline_id>/stages/create/', views.stage_create, name='stage-create'),
    path(
        'pipelines/<int:pipeline_id>/stages/<int:stage_id>/edit/',
        views.stage_edit,
        name='stage-edit',
    ),
    path(
        'pipelines/<int:pipeline_id>/stages/<int:stage_id>/delete/',
        views.stage_delete,
        name='stage-delete',
    ),
    path(
        'pipelines/<int:pipeline_id>/stages/reorder/',
        views.stage_reorder,
        name='stage-reorder',
    ),
    path('pipelines/<int:pipeline_id>/cards/create/', views.card_create, name='card-create'),
    path(
        'pipelines/<int:pipeline_id>/cards/<int:card_id>/edit/',
        views.card_edit,
        name='card-edit',
    ),
    path(
        'pipelines/<int:pipeline_id>/cards/<int:card_id>/delete/',
        views.card_delete,
        name='card-delete',
    ),
    path(
        'pipelines/<int:pipeline_id>/cards/<int:card_id>/move/',
        views.card_move,
        name='card-move',
    ),
]
