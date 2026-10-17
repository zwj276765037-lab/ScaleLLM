"""Isolation checks for resource supervision; never signal real foreign tasks."""
import os
from pathlib import Path
import signal
import unittest
from unittest.mock import patch

from vivado.scripts.run_managed_eda import owned_processes, process_table, terminate_owned


def row(ppid, pgrp, start):
    return {"ppid": ppid, "pgrp": pgrp, "start_ticks": start, "rss_bytes": 4096}


class ManagedEdaIsolationTests(unittest.TestCase):
    def test_foreign_process_and_reused_pid_are_not_owned(self):
        table = {100: row(1, 100, 20), 101: row(100, 100, 21),
                 200: row(1, 200, 30), 201: row(200, 200, 31)}
        tracked = {200: 29}
        self.assertEqual(set(owned_processes(table, 100, tracked)), {100, 101})
        self.assertEqual(tracked[200], 29)

    def test_detached_descendant_stays_owned_after_reparenting(self):
        tracked = {}
        first = {100: row(1, 100, 20), 101: row(100, 101, 21),
                 102: row(101, 102, 22), 200: row(1, 200, 30)}
        self.assertEqual(set(owned_processes(first, 100, tracked)), {100, 101, 102})
        second = {102: row(1, 102, 22), 200: row(1, 200, 30)}
        self.assertEqual(set(owned_processes(second, 100, tracked)), {102})

    def test_cleanup_signals_only_current_owned_identities(self):
        initial = {100: row(1, 100, 20), 101: row(100, 101, 21),
                   200: row(1, 200, 30)}
        with patch("vivado.scripts.run_managed_eda.process_table", side_effect=[initial, {}, {}]), \
             patch("vivado.scripts.run_managed_eda.os.kill") as kill, \
             patch("vivado.scripts.run_managed_eda.time.sleep"):
            self.assertEqual(terminate_owned(100, {200: 29}), [])
        self.assertEqual(kill.call_args_list[0].args, (100, signal.SIGTERM))
        self.assertEqual(kill.call_args_list[1].args, (101, signal.SIGTERM))
        self.assertEqual(kill.call_count, 2)

    def test_proc_parser_matches_own_kernel_parent_and_niceness(self):
        me = process_table()[os.getpid()]
        self.assertEqual(me["ppid"], os.getppid())
        self.assertEqual(me["nice"], os.getpriority(os.PRIO_PROCESS, 0))
        self.assertGreater(me["rss_bytes"], 0)
        self.assertGreater(me["start_ticks"], 0)
