import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Pipeline, PipelineCard, PipelineStage


User = get_user_model()


class PipelineTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='test-pass-123')
        self.other_user = User.objects.create_user(username='other', password='test-pass-123')

    def make_pipeline(self, *, owner=None, name='Sales'):
        return Pipeline.objects.create(name=name, owner=owner or self.user)

    def make_stage(self, pipeline, *, name='New', position=1):
        return PipelineStage.objects.create(pipeline=pipeline, name=name, position=position)

    def make_card(self, pipeline, stage, *, title='Acme', position=1):
        return PipelineCard.objects.create(
            pipeline=pipeline,
            stage=stage,
            title=title,
            position=position,
            created_by=self.user,
        )


class PipelineModelTests(PipelineTestCase):
    def test_creating_pipeline_stores_owner(self):
        pipeline = self.make_pipeline()

        self.assertEqual(pipeline.owner, self.user)
        self.assertEqual(str(pipeline), 'Sales')

    def test_stage_ordering_is_deterministic(self):
        pipeline = self.make_pipeline()
        later = self.make_stage(pipeline, name='Won', position=2)
        first = self.make_stage(pipeline, name='New', position=1)

        self.assertEqual(list(pipeline.stages.all()), [first, later])

    def test_card_ordering_is_deterministic(self):
        pipeline = self.make_pipeline()
        stage = self.make_stage(pipeline)
        later = self.make_card(pipeline, stage, title='Later', position=2)
        first = self.make_card(pipeline, stage, title='First', position=1)

        self.assertEqual(list(stage.cards.all()), [first, later])

    def test_card_cannot_use_stage_from_another_pipeline(self):
        pipeline = self.make_pipeline()
        other_pipeline = self.make_pipeline(name='Other')
        foreign_stage = self.make_stage(other_pipeline)
        card = PipelineCard(
            pipeline=pipeline,
            stage=foreign_stage,
            title='Invalid',
            position=1,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            card.save()


class PipelineWorkflowTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_create_pipeline_creates_default_stages(self):
        response = self.client.post(
            reverse('pipelines:create'),
            {'name': 'Recruiting', 'description': 'Candidate workflow'},
        )
        pipeline = Pipeline.objects.get(name='Recruiting')

        self.assertRedirects(response, reverse('pipelines:detail', args=[pipeline.pk]))
        self.assertEqual(pipeline.owner, self.user)
        self.assertEqual(
            list(pipeline.stages.values_list('name', 'position')),
            [('New', 1), ('In Progress', 2), ('Won', 3), ('Lost', 4)],
        )

    def test_pipeline_list_update_and_delete(self):
        pipeline = self.make_pipeline()

        list_response = self.client.get(reverse('pipelines:list'))
        self.assertContains(list_response, pipeline.name)

        update_response = self.client.post(
            reverse('pipelines:edit', args=[pipeline.pk]),
            {'name': 'Updated Sales', 'description': 'Updated description'},
        )
        self.assertRedirects(update_response, reverse('pipelines:detail', args=[pipeline.pk]))
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.name, 'Updated Sales')

        delete_response = self.client.post(reverse('pipelines:delete', args=[pipeline.pk]))
        self.assertRedirects(delete_response, reverse('pipelines:list'))
        self.assertFalse(Pipeline.objects.filter(pk=pipeline.pk).exists())

    def test_stage_create_rename_reorder_and_safe_deletion(self):
        pipeline = self.make_pipeline()
        new_stage = self.make_stage(pipeline, name='New', position=1)
        won_stage = self.make_stage(pipeline, name='Won', position=2)

        create_response = self.client.post(
            reverse('pipelines:stage-create', args=[pipeline.pk]), {'name': 'Qualified'}
        )
        self.assertRedirects(create_response, reverse('pipelines:detail', args=[pipeline.pk]))
        qualified = pipeline.stages.get(name='Qualified')
        self.assertEqual(qualified.position, 3)

        rename_response = self.client.post(
            reverse('pipelines:stage-edit', args=[pipeline.pk, qualified.pk]), {'name': 'Proposal'}
        )
        self.assertEqual(rename_response.status_code, 302)
        qualified.refresh_from_db()
        self.assertEqual(qualified.name, 'Proposal')

        ordered_ids = [qualified.pk, new_stage.pk, won_stage.pk]
        reorder_response = self.client.post(
            reverse('pipelines:stage-reorder', args=[pipeline.pk]),
            data=json.dumps({'stage_ids': ordered_ids}),
            content_type='application/json',
        )
        self.assertEqual(reorder_response.status_code, 200)
        self.assertEqual(list(pipeline.stages.values_list('id', flat=True)), ordered_ids)

        card = self.make_card(pipeline, qualified)
        delete_response = self.client.post(
            reverse('pipelines:stage-delete', args=[pipeline.pk, qualified.pk])
        )
        self.assertRedirects(delete_response, reverse('pipelines:detail', args=[pipeline.pk]))
        self.assertTrue(PipelineStage.objects.filter(pk=qualified.pk).exists())
        self.assertTrue(PipelineCard.objects.filter(pk=card.pk).exists())

    def test_card_create_edit_and_delete(self):
        pipeline = self.make_pipeline()
        new_stage = self.make_stage(pipeline)
        won_stage = self.make_stage(pipeline, name='Won', position=2)
        card_data = {
            'title': 'Acme opportunity',
            'description': 'Follow up this week',
            'contact_name': 'Avery Smith',
            'company': 'Acme Corp',
            'email': 'avery@example.com',
            'phone': '555-0100',
            'value': '12000.00',
            'due_date': '2026-08-20',
            'stage': new_stage.pk,
        }
        create_response = self.client.post(reverse('pipelines:card-create', args=[pipeline.pk]), card_data)
        card = PipelineCard.objects.get(title='Acme opportunity')

        self.assertRedirects(create_response, reverse('pipelines:detail', args=[pipeline.pk]))
        self.assertEqual(card.position, 1)
        self.assertEqual(card.created_by, self.user)

        card_data.update({'title': 'Acme closed', 'stage': won_stage.pk})
        edit_response = self.client.post(
            reverse('pipelines:card-edit', args=[pipeline.pk, card.pk]), card_data
        )
        self.assertRedirects(edit_response, reverse('pipelines:detail', args=[pipeline.pk]))
        card.refresh_from_db()
        self.assertEqual(card.title, 'Acme closed')
        self.assertEqual(card.stage, won_stage)

        delete_response = self.client.post(reverse('pipelines:card-delete', args=[pipeline.pk, card.pk]))
        self.assertRedirects(delete_response, reverse('pipelines:detail', args=[pipeline.pk]))
        self.assertFalse(PipelineCard.objects.filter(pk=card.pk).exists())

    def test_card_move_between_stages_and_reorder_within_stage(self):
        pipeline = self.make_pipeline()
        new_stage = self.make_stage(pipeline)
        won_stage = self.make_stage(pipeline, name='Won', position=2)
        first = self.make_card(pipeline, new_stage, title='First', position=1)
        second = self.make_card(pipeline, new_stage, title='Second', position=2)
        third = self.make_card(pipeline, won_stage, title='Third', position=1)

        move_response = self.client.post(
            reverse('pipelines:card-move', args=[pipeline.pk, second.pk]),
            data=json.dumps(
                {
                    'card_id': second.pk,
                    'destination_stage_id': won_stage.pk,
                    'position': 0,
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(move_response.status_code, 200)
        second.refresh_from_db()
        third.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual((second.stage, second.position), (won_stage, 1))
        self.assertEqual((third.stage, third.position), (won_stage, 2))
        self.assertEqual(first.position, 1)

        reorder_response = self.client.post(
            reverse('pipelines:card-move', args=[pipeline.pk, third.pk]),
            data=json.dumps(
                {
                    'card_id': third.pk,
                    'destination_stage_id': won_stage.pk,
                    'position': 0,
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(reorder_response.status_code, 200)
        second.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual((third.position, second.position), (1, 2))


class AccessAndSecurityTests(PipelineTestCase):
    def test_user_can_log_in_and_log_out(self):
        login_response = self.client.post(
            reverse('login'),
            {'username': self.user.username, 'password': 'test-pass-123'},
        )

        self.assertRedirects(login_response, reverse('pipelines:list'))
        logout_response = self.client.post(reverse('logout'))
        self.assertRedirects(logout_response, reverse('login'))

    def test_anonymous_user_is_redirected_from_pipelines(self):
        response = self.client.get(reverse('pipelines:list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_owner_can_open_own_pipeline(self):
        pipeline = self.make_pipeline()
        self.client.force_login(self.user)

        response = self.client.get(reverse('pipelines:detail', args=[pipeline.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pipeline.name)

    def test_user_cannot_access_or_edit_another_users_pipeline(self):
        other_pipeline = self.make_pipeline(owner=self.other_user)
        self.client.force_login(self.user)

        detail_response = self.client.get(reverse('pipelines:detail', args=[other_pipeline.pk]))
        edit_response = self.client.post(
            reverse('pipelines:edit', args=[other_pipeline.pk]),
            {'name': 'Not allowed', 'description': ''},
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(edit_response.status_code, 404)
        other_pipeline.refresh_from_db()
        self.assertEqual(other_pipeline.name, 'Sales')

    def test_user_cannot_modify_another_users_card(self):
        other_pipeline = self.make_pipeline(owner=self.other_user)
        other_stage = self.make_stage(other_pipeline)
        other_card = PipelineCard.objects.create(
            pipeline=other_pipeline,
            stage=other_stage,
            title='Private',
            position=1,
            created_by=self.other_user,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('pipelines:card-delete', args=[other_pipeline.pk, other_card.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PipelineCard.objects.filter(pk=other_card.pk).exists())

    def test_cross_pipeline_card_move_and_invalid_stage_are_rejected(self):
        pipeline = self.make_pipeline()
        source = self.make_stage(pipeline)
        card = self.make_card(pipeline, source)
        other_pipeline = self.make_pipeline(name='Other', owner=self.other_user)
        foreign_stage = self.make_stage(other_pipeline)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('pipelines:card-move', args=[pipeline.pk, card.pk]),
            data=json.dumps(
                {
                    'card_id': card.pk,
                    'destination_stage_id': foreign_stage.pk,
                    'position': 0,
                }
            ),
            content_type='application/json',
        )
        invalid_response = self.client.post(
            reverse('pipelines:card-move', args=[pipeline.pk, card.pk]),
            data=json.dumps(
                {'card_id': card.pk, 'destination_stage_id': 999999, 'position': 0}
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(invalid_response.status_code, 404)
        card.refresh_from_db()
        self.assertEqual(card.stage, source)

    def test_state_changing_get_requests_are_rejected(self):
        pipeline = self.make_pipeline()
        stage = self.make_stage(pipeline)
        card = self.make_card(pipeline, stage)
        self.client.force_login(self.user)

        stage_response = self.client.get(reverse('pipelines:stage-delete', args=[pipeline.pk, stage.pk]))
        move_response = self.client.get(reverse('pipelines:card-move', args=[pipeline.pk, card.pk]))

        self.assertEqual(stage_response.status_code, 405)
        self.assertEqual(move_response.status_code, 405)

# Create your tests here.
