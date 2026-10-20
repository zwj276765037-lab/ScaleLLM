"""E003 authorization, cross-attempt budget and full-route completion checks; no EDA."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_m002_physical_diagnostic import m
import test_m002_pre_place_recovery as recovery_tests
import m002_execution_profile as p
from vivado.scripts import run_managed_eda as manager


class FullImplementationProfile(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.base=self.root/p.EXPERIMENT/'experiment_results'
        self.contract=self.root/p.CONTRACT;self.contract.parent.mkdir(parents=True);self.contract.write_text('frozen contract')
        self.patch=patch.object(p,'CONTRACT_SHA',p.identity(self.contract)['sha256']);self.patch.start();self.addCleanup(self.patch.stop)
        self.attempt=self.base/'runs/R002/attempts/AT001_place';self.attempt.mkdir(parents=True)
        self.report=self.root/'report';self.report.mkdir()
        self.t0=dt.datetime(2026,10,15,tzinfo=dt.timezone.utc)

    def bind(self):
        auth=p.authorization(self.root,'place',self.attempt,self.report)
        p.save(self.attempt/'execution_authorization.json',auth);p.save(self.report/'execution_authorization.json',auth)
        p.save(self.attempt/'command.json',dict(execution_profile=p.PROFILE,stage='place',report=str(self.report),
            authorization=p.identity(self.attempt/'execution_authorization.json'),started_utc=self.t0.isoformat()))
        return auth

    def closed(self,stage='place',number=1,start=0,duration=100,launch=True):
        run='R002' if stage=='place' else 'R003';a=self.base/f'runs/{run}/attempts/AT{number:03d}_cost';a.mkdir(parents=True)
        p.save(a/'command.json',dict(stage=stage,execution_profile=p.PROFILE,started_utc=(self.t0+dt.timedelta(seconds=start)).isoformat()))
        p.save(a/'status.json',dict(stage=stage,execution_state='completed',owned_survivors=[],ended_utc=(self.t0+dt.timedelta(seconds=start+duration)).isoformat()))
        if launch:
            receipt=dict(launched_utc=(self.t0+dt.timedelta(seconds=start+10)).isoformat(),pid=123,managed_attempt=str(a))
            p.save(a/'actual_eda_started.json',receipt)
            if not (self.base/'physical_budget_anchor.json').exists():p.save(self.base/'physical_budget_anchor.json',receipt)
        return a

    def test_explicit_contract_and_manager_record_bind_report(self):
        auth=self.bind();self.assertEqual(p.report_authorization(self.report),auth);self.assertFalse(auth['single_bounded_restart'])

    def test_changed_contract_and_wrong_stage_root_rejected(self):
        self.contract.write_text('changed')
        with self.assertRaisesRegex(ValueError,'contract identity'):self.bind()
        with self.assertRaisesRegex(ValueError,'stage/attempt'):p.authorization(self.root,'route',self.attempt,self.report)

    def test_env_or_report_marker_alone_cannot_authorize(self):
        auth=p.authorization(self.root,'place',self.attempt,self.report);p.save(self.report/'execution_authorization.json',auth)
        with self.assertRaises(FileNotFoundError):p.report_authorization(self.report)
        self.bind();command=json.loads((self.attempt/'command.json').read_text());command['execution_profile']='legacy';p.save(self.attempt/'command.json',command)
        with self.assertRaisesRegex(ValueError,'binding mismatch'):p.report_authorization(self.report)

    def test_mutated_report_authorization_rejected(self):
        auth=self.bind();auth['stage_cumulative_seconds']=999999;p.save(self.report/'execution_authorization.json',auth)
        with self.assertRaisesRegex(ValueError,'authorization changed'):p.report_authorization(self.report)

    def test_pre_eda_failure_cost_counts_without_starting_global_clock(self):
        self.closed(duration=31,launch=False);b=p.budget(self.root,'place',self.t0+dt.timedelta(days=5))
        self.assertEqual(b['stage_used_seconds'],31);self.assertIsNone(b['global_deadline_utc'])

    def test_retry_cannot_reset_stage_cost_and_global_includes_repair_gaps(self):
        self.closed(duration=100);self.closed(number=2,start=500,duration=200)
        b=p.budget(self.root,'place',self.t0+dt.timedelta(seconds=900))
        self.assertEqual(b['stage_remaining_seconds'],42900);self.assertEqual(b['global_remaining_seconds'],85510)
        self.assertEqual(b['effective_timeout_seconds'],42900)

    def test_route_separate_stage_cost_but_shared_global_deadline(self):
        self.closed(duration=42000);self.closed('route',start=50000,duration=1000)
        b=p.budget(self.root,'route',self.t0+dt.timedelta(seconds=80000))
        self.assertEqual(b['stage_used_seconds'],1000);self.assertEqual(b['effective_timeout_seconds'],6410)

    def test_unclosed_or_live_survivor_never_counts_as_free(self):
        a=self.closed();(a/'status.json').unlink()
        with self.assertRaisesRegex(ValueError,'unclosed E003 attempt'):p.budget(self.root,'place',self.t0)
        p.save(a/'status.json',dict(execution_state='completed',owned_survivors=[123]))
        with self.assertRaisesRegex(ValueError,'process ownership'):p.budget(self.root,'place',self.t0)

    def test_stage_or_global_exhaustion_rejected(self):
        self.closed(duration=43201)
        with self.assertRaisesRegex(ValueError,'exhausted'):p.budget(self.root,'place',self.t0)
        with self.assertRaisesRegex(ValueError,'exhausted'):p.budget(self.root,'route',self.t0+dt.timedelta(seconds=86411))

    def test_anchor_loss_or_rewrite_rejected(self):
        self.closed();p.save(self.base/'physical_budget_anchor.json',{'launched_utc':self.t0.isoformat()})
        with self.assertRaisesRegex(ValueError,'anchor missing/changed'):p.budget(self.root,'place',self.t0)

    def test_real_spawn_receipt_sets_anchor_once_and_later_launch_preserves_it(self):
        self.bind()
        with patch.object(p,'now',return_value=self.t0):first=p.record_launch(self.report,100)
        self.assertEqual(json.loads((self.base/'physical_budget_anchor.json').read_text()),first)
        # Subsequent successful spawn uses a different managed/report identity.
        second=self.base/'runs/R002/attempts/AT002_place';second.mkdir();other=self.root/'report2';other.mkdir()
        auth=p.authorization(self.root,'place',second,other);p.save(second/'execution_authorization.json',auth);p.save(other/'execution_authorization.json',auth)
        p.save(second/'command.json',dict(stage='place',execution_profile=p.PROFILE,report=str(other),authorization=p.identity(second/'execution_authorization.json')))
        with patch.object(p,'now',return_value=self.t0+dt.timedelta(seconds=100)):p.record_launch(other,101)
        self.assertEqual(json.loads((self.base/'physical_budget_anchor.json').read_text()),first)

    def test_route_requires_positive_exact_fully_routed_and_all_zero_errors(self):
        complete=dict(routable=10,fully_routed=10,unrouted=0,partially_routed=0,routing_errors=0)
        p.require_complete_route(complete)
        for key,value in [('routable',0),('fully_routed',9),('unrouted',1),('partially_routed',1),('routing_errors',1)]:
            with self.assertRaisesRegex(ValueError,'not fully routed'):p.require_complete_route({**complete,key:value})

    def test_legacy_limits_remain_two_hours(self):
        self.assertEqual(manager.LIMITS,dict(create=1800,synth=10800,place=7200,route=7200))


class NewAuthorizedRestore(unittest.TestCase):
    def test_new_authorization_changes_only_policy_and_keeps_original_receipts(self):
        fixture=recovery_tests.CompletedPrePlaceParent("test_timeout_restarts_saved_pre_place_and_keeps_history_at_original_paths")
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        auth={'profile':p.PROFILE,'contract':{'sha256':p.CONTRACT_SHA}}
        with patch.object(p,'report_authorization',return_value=auth):value=fixture.check()
        self.assertEqual(value['execution_authorization'],auth);self.assertFalse(value['single_bounded_restart'])
        self.assertEqual(value['checkpoint'],fixture.saved)
        self.assertTrue(all(Path(row['path']).parent==fixture.source for row in value['historical_command_receipts'].values()))
