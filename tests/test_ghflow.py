"""The three gates on GitHub writes, as the owner stated them.

    commit+push ke branch baru; PR hanya ke dev; merge hanya setelah approval
    lewat Telegram.

Every test here is one way that rule could be broken. The merge tests matter
most: an approval that can be replayed onto a rewritten PR would let an agent
change what the owner actually agreed to after the fact.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))

import ghflow  # noqa: E402


class RepoScopeTests(unittest.TestCase):
    def test_owner_orgs_pass(self):
        for repo in ("Nexora-Tech-Team/NEXONE", "NexoraTechTeam/accreditation"):
            self.assertTrue(ghflow.validate_repo(repo)[0], repo)

    def test_other_org_refused(self):
        ok, reason = ghflow.validate_repo("someone-else/accreditation")
        self.assertFalse(ok)
        self.assertIn("refused", reason)

    def test_malformed_names_refused(self):
        for bad in ("", "nexora", "a/b/c", "NexoraTechTeam/"):
            self.assertFalse(ghflow.validate_repo(bad)[0], bad)


class BaseBranchTests(unittest.TestCase):
    def test_dev_is_the_only_base(self):
        self.assertTrue(ghflow.validate_base("dev")[0])

    def test_protected_branches_refused_by_name(self):
        for bad in ("main", "master", "production", "prod", "staging", "release"):
            ok, reason = ghflow.validate_base(bad)
            self.assertFalse(ok, bad)
            self.assertIn("refused", reason)

    def test_unknown_branch_refused_even_if_harmless(self):
        # Allowlist, not blocklist: a new branch name is refused by default.
        self.assertFalse(ghflow.validate_base("feature/x")[0])

    def test_case_insensitive(self):
        self.assertFalse(ghflow.validate_base("MAIN")[0])


class HeadBranchTests(unittest.TestCase):
    def test_agent_branch_must_be_namespaced(self):
        self.assertTrue(ghflow.validate_head("ah/fix-login-20260919-101500")[0])

    def test_shared_branches_refused_as_push_target(self):
        for bad in ("dev", "main", "master", "staging", "production"):
            self.assertFalse(ghflow.validate_head(bad)[0], bad)

    def test_unnamespaced_branch_refused(self):
        self.assertFalse(ghflow.validate_head("hotfix")[0])

    def test_traversal_and_spaces_refused(self):
        for bad in ("ah/../dev", "ah/two words", "ah/"):
            self.assertFalse(ghflow.validate_head(bad)[0], bad)

    def test_minted_branch_is_valid_and_prefixed(self):
        name = ghflow.branch_for("135157-520a")
        self.assertTrue(name.startswith("ah/"))
        self.assertTrue(ghflow.validate_head(name)[0])

    def test_minted_branch_sanitises_hostile_task_id(self):
        name = ghflow.branch_for("../../dev")
        self.assertTrue(ghflow.validate_head(name)[0])
        self.assertNotIn("..", name)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_roundtrip(self):
        ghflow.record_approval("NexoraTechTeam/academy", 7, "abc1234", 6687943152, self.dir)
        rec = ghflow.read_approval("NexoraTechTeam/academy", 7, self.dir)
        self.assertEqual(rec["number"], 7)
        self.assertEqual(rec["approved_by"], "6687943152")

    def test_missing_approval_blocks_merge(self):
        ok, reason = ghflow.approval_matches(None, "NexoraTechTeam/academy", 7, "abc1234")
        self.assertFalse(ok)
        self.assertIn("belum ada approval", reason)

    def test_approval_for_another_pr_does_not_transfer(self):
        ghflow.record_approval("NexoraTechTeam/academy", 7, "abc1234", 1, self.dir)
        rec = ghflow.read_approval("NexoraTechTeam/academy", 7, self.dir)
        ok, _ = ghflow.approval_matches(rec, "NexoraTechTeam/academy", 8, "abc1234")
        self.assertFalse(ok)

    def test_approval_does_not_survive_a_new_commit(self):
        ghflow.record_approval("NexoraTechTeam/academy", 7, "abc1234", 1, self.dir)
        rec = ghflow.read_approval("NexoraTechTeam/academy", 7, self.dir)
        ok, reason = ghflow.approval_matches(rec, "NexoraTechTeam/academy", 7, "def5678")
        self.assertFalse(ok)
        self.assertIn("approval ulang", reason)

    def test_approval_refuses_foreign_repo(self):
        with self.assertRaises(ValueError):
            ghflow.record_approval("evil/repo", 1, "abc", 1, self.dir)


class TokenResolutionTests(unittest.TestCase):
    """A fine-grained PAT belongs to one owner; the harness writes to two."""

    def setUp(self):
        self.saved = {k: ghflow.os.environ.get(k) for k in
                      ("GITHUB_PAT", "GITHUB_TOKEN", "GITHUB_ORGS_PAT",
                       "GITHUB_PAT_NEXORATECHTEAM")}

        def restore():
            for k, v in self.saved.items():
                if v is None:
                    ghflow.os.environ.pop(k, None)
                else:
                    ghflow.os.environ[k] = v

        self.addCleanup(restore)
        for k in self.saved:
            ghflow.os.environ.pop(k, None)

    def test_org_specific_token_wins_for_that_org(self):
        ghflow.os.environ["GITHUB_PAT"] = "generic"
        ghflow.os.environ["GITHUB_PAT_NEXORATECHTEAM"] = "org-token"
        self.assertEqual(ghflow.token("NexoraTechTeam/academy"), "org-token")

    def test_other_owner_falls_back_to_the_generic_token(self):
        ghflow.os.environ["GITHUB_PAT"] = "generic"
        ghflow.os.environ["GITHUB_PAT_NEXORATECHTEAM"] = "org-token"
        self.assertEqual(ghflow.token("Nexora-Tech-Team/NEXONE"), "generic")

    def test_a_single_classic_token_still_covers_everything(self):
        ghflow.os.environ["GITHUB_PAT"] = "classic"
        for repo in ("NexoraTechTeam/academy", "Nexora-Tech-Team/NEXONE", ""):
            self.assertEqual(ghflow.token(repo), "classic")

    def test_no_token_is_empty_not_an_exception(self):
        self.assertEqual(ghflow.token("NexoraTechTeam/academy"), "")

    def test_org_repos_use_the_org_token(self):
        # Measured: GITHUB_PAT 403s on org repos, GITHUB_ORGS_PAT does not.
        ghflow.os.environ["GITHUB_PAT"] = "personal"
        ghflow.os.environ["GITHUB_ORGS_PAT"] = "org"
        self.assertEqual(ghflow.token("NexoraTechTeam/academy"), "org")

    def test_personal_repos_use_the_personal_token(self):
        ghflow.os.environ["GITHUB_PAT"] = "personal"
        ghflow.os.environ["GITHUB_ORGS_PAT"] = "org"
        self.assertEqual(ghflow.token("Nexora-Tech-Team/NEXONE"), "personal")

    def test_explicit_per_owner_override_beats_both(self):
        ghflow.os.environ["GITHUB_PAT"] = "personal"
        ghflow.os.environ["GITHUB_ORGS_PAT"] = "org"
        ghflow.os.environ["GITHUB_PAT_NEXORATECHTEAM"] = "explicit"
        self.assertEqual(ghflow.token("NexoraTechTeam/academy"), "explicit")


class PushTests(unittest.TestCase):
    class FakeProc:
        def __init__(self, rc=0, out="", err=""):
            self.returncode, self.stdout, self.stderr = rc, out, err

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wt = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.old = ghflow.os.environ.get("GITHUB_PAT")
        ghflow.os.environ["GITHUB_PAT"] = "ghp_secrettoken"
        self.addCleanup(lambda: ghflow.os.environ.__setitem__("GITHUB_PAT", self.old or ""))

    def test_push_refuses_shared_branch_before_touching_git(self):
        calls = []
        res = ghflow.push_branch(self.wt, "NexoraTechTeam/academy", "dev",
                                 caller=lambda a: calls.append(a))
        self.assertFalse(res["ok"])
        self.assertEqual(calls, [], "git must not run for a refused branch")

    def test_push_refuses_foreign_repo(self):
        calls = []
        res = ghflow.push_branch(self.wt, "evil/repo", "ah/x-1",
                                 caller=lambda a: calls.append(a))
        self.assertFalse(res["ok"])
        self.assertEqual(calls, [])

    def test_push_uses_head_refspec_to_the_new_branch(self):
        seen = {}

        def caller(args):
            seen["args"] = args
            return self.FakeProc(0, "done")

        res = ghflow.push_branch(self.wt, "NexoraTechTeam/academy", "ah/x-1", caller=caller)
        self.assertTrue(res["ok"], res)
        self.assertIn("HEAD:refs/heads/ah/x-1", seen["args"])

    def test_token_is_never_returned_in_output(self):
        def caller(args):
            return self.FakeProc(1, "", "fatal: https://x-access-token:ghp_secrettoken@github.com denied")

        res = ghflow.push_branch(self.wt, "NexoraTechTeam/academy", "ah/x-1", caller=caller)
        self.assertFalse(res["ok"])
        self.assertNotIn("ghp_secrettoken", json.dumps(res))
        self.assertIn("***", res["error"])


class MergeGateTests(unittest.TestCase):
    """merge() must refuse before it ever reaches the network."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.calls = []
        self.pr = {"ok": True, "number": 7, "title": "x", "base": "dev",
                   "head": "ah/x-1", "head_sha": "abc1234", "state": "open", "merged": False}
        self._real_get, self._real_api = ghflow.get_pr, ghflow._api
        ghflow.get_pr = lambda repo, number: dict(self.pr)
        ghflow._api = lambda *a, **k: self.calls.append(a) or (200, {"sha": "merged"})
        self.addCleanup(lambda: (setattr(ghflow, "get_pr", self._real_get),
                                 setattr(ghflow, "_api", self._real_api)))

    def test_no_approval_means_no_api_call(self):
        res = ghflow.merge("NexoraTechTeam/academy", 7, self.dir)
        self.assertFalse(res["ok"])
        self.assertEqual(self.calls, [], "merge must not reach GitHub without approval")

    def test_approval_allows_the_merge(self):
        ghflow.record_approval("NexoraTechTeam/academy", 7, "abc1234", 6687943152, self.dir)
        res = ghflow.merge("NexoraTechTeam/academy", 7, self.dir)
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(self.calls), 1)

    def test_pr_targeting_main_is_refused_even_with_approval(self):
        self.pr["base"] = "main"
        ghflow.record_approval("NexoraTechTeam/academy", 7, "abc1234", 1, self.dir)
        res = ghflow.merge("NexoraTechTeam/academy", 7, self.dir)
        self.assertFalse(res["ok"])
        self.assertEqual(self.calls, [])

    def test_rewritten_pr_is_refused_after_approval(self):
        ghflow.record_approval("NexoraTechTeam/academy", 7, "abc1234", 1, self.dir)
        self.pr["head_sha"] = "def5678"
        res = ghflow.merge("NexoraTechTeam/academy", 7, self.dir)
        self.assertFalse(res["ok"])
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
