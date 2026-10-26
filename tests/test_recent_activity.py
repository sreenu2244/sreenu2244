import unittest

from scripts.update_recent_activity import format_activity, replace_activity


class RecentActivityTests(unittest.TestCase):
    def test_formats_public_events_without_exposing_commit_messages(self):
        events = [
            {
                "type": "PushEvent",
                "repo": {"name": "owner/project"},
                "created_at": "2026-10-25T12:30:00Z",
                "payload": {"commits": [{"message": "private detail"}]},
            },
            {
                "type": "PullRequestEvent",
                "repo": {"name": "owner/project"},
                "created_at": "2026-10-24T08:00:00Z",
                "payload": {"action": "opened", "number": 12},
            },
        ]

        result = format_activity(events)

        self.assertIn("**2026-10-25** — Pushed to [owner/project]", result)
        self.assertIn("https://github.com/owner/project/pull/12", result)
        self.assertNotIn("private detail", result)

    def test_limits_output_and_ignores_unlisted_event_types(self):
        events = [
            {
                "type": "WatchEvent",
                "repo": {"name": "owner/noise"},
                "created_at": "2026-10-26T00:00:00Z",
            }
        ] + [
            {
                "type": "PushEvent",
                "repo": {"name": f"owner/project-{index}"},
                "created_at": "2026-10-25T12:30:00Z",
            }
            for index in range(8)
        ]

        result = format_activity(events)

        self.assertEqual(result.count("\n"), 4)
        self.assertNotIn("owner/noise", result)
        self.assertNotIn("owner/project-5", result)

    def test_returns_placeholder_when_no_supported_activity_exists(self):
        self.assertEqual(
            format_activity([{"type": "WatchEvent", "repo": {"name": "owner/project"}}]),
            "_No recent public activity found._",
        )

    def test_skips_malformed_event_payloads(self):
        events = [
            {
                "type": "IssuesEvent",
                "repo": {"name": "owner/project"},
                "created_at": "2026-10-25T12:30:00Z",
                "payload": None,
            },
            {
                "type": "IssuesEvent",
                "repo": {"name": "owner/project"},
                "created_at": "2026-10-25T12:30:00Z",
                "payload": {"action": "opened", "issue": None},
            },
        ]

        self.assertEqual(format_activity(events), "_No recent public activity found._")

    def test_replaces_only_the_marked_activity_region(self):
        readme = f"before\n{START}\nold item\n{END}\nafter"

        updated = replace_activity(readme, "- new item")

        self.assertEqual(updated, f"before\n{START}\n- new item\n{END}\nafter")
        self.assertEqual(replace_activity(updated, "- new item"), updated)

    def test_requires_a_single_ordered_marker_pair(self):
        with self.assertRaises(ValueError):
            replace_activity("missing markers", "activity")
        with self.assertRaises(ValueError):
            replace_activity(f"{END}\n{START}", "activity")


START = "<!-- recent-activity:start -->"
END = "<!-- recent-activity:end -->"


if __name__ == "__main__":
    unittest.main()
