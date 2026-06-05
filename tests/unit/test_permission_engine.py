"""Unit tests for the permission matching engine.

Tests the deterministic constraint evaluation: exact match, contains, regex,
AND logic, list fields, circuit breaker, and multi-permission evaluation.
"""

import pytest

from jarvis.services.permission_engine import (
    MAX_MATCHES_PER_PERMISSION,
    check_circuit_breaker,
    evaluate_permissions,
    extract_items,
    match_item,
)


# ---------------------------------------------------------------------------
# match_item — single item against constraints
# ---------------------------------------------------------------------------


class TestMatchItemExact:
    def test_exact_match(self):
        assert match_item({"sender": "jenkins@ci.com"}, {"sender": "jenkins@ci.com"})

    def test_exact_match_case_insensitive(self):
        assert match_item({"sender": "Jenkins@CI.com"}, {"sender": "jenkins@ci.com"})

    def test_exact_no_match(self):
        assert not match_item({"sender": "alice@team.com"}, {"sender": "jenkins@ci.com"})

    def test_exact_missing_field(self):
        assert not match_item({"subject": "hello"}, {"sender": "jenkins@ci.com"})

    def test_exact_match_list_field(self):
        assert match_item({"labels": ["inbox", "alerts"]}, {"labels": "alerts"})

    def test_exact_no_match_list_field(self):
        assert not match_item({"labels": ["inbox"]}, {"labels": "alerts"})

    def test_exact_match_list_case_insensitive(self):
        assert match_item({"labels": ["ALERTS", "Inbox"]}, {"labels": "alerts"})


class TestMatchItemContains:
    def test_contains_match(self):
        assert match_item(
            {"subject": "Build failed #123"},
            {"subject_contains": "build failed"},
        )

    def test_contains_case_insensitive(self):
        assert match_item(
            {"subject": "BUILD FAILED"},
            {"subject_contains": "build failed"},
        )

    def test_contains_no_match(self):
        assert not match_item(
            {"subject": "Deploy success"},
            {"subject_contains": "build failed"},
        )

    def test_contains_missing_field(self):
        assert not match_item({}, {"subject_contains": "anything"})

    def test_contains_partial_substring(self):
        assert match_item(
            {"sender": "jenkins-noreply@company.com"},
            {"sender_contains": "jenkins"},
        )


class TestMatchItemRegex:
    def test_regex_match(self):
        assert match_item({"repo": "team-platform"}, {"repo_matches": "^team-.*"})

    def test_regex_no_match(self):
        assert not match_item({"repo": "personal-stuff"}, {"repo_matches": "^team-.*"})

    def test_regex_case_insensitive(self):
        assert match_item({"repo": "Team-Platform"}, {"repo_matches": "^team-.*"})

    def test_regex_missing_field(self):
        assert not match_item({}, {"repo_matches": "^team-.*"})

    def test_regex_invalid_pattern_no_crash(self):
        assert not match_item({"title": "hello"}, {"title_matches": "[invalid"})

    def test_regex_partial_match(self):
        assert match_item(
            {"title": "fix: update docs for API"},
            {"title_matches": "docs"},
        )


class TestMatchItemAndLogic:
    def test_all_constraints_must_match(self):
        item = {"sender": "jenkins@ci.com", "subject": "Build failed"}
        assert match_item(item, {"sender_contains": "jenkins", "subject_contains": "failed"})

    def test_one_constraint_fails(self):
        item = {"sender": "jenkins@ci.com", "subject": "Build success"}
        assert not match_item(item, {"sender_contains": "jenkins", "subject_contains": "failed"})

    def test_empty_constraints_always_match(self):
        assert match_item({"anything": "value"}, {})

    def test_mixed_constraint_types(self):
        item = {"sender": "ci@jenkins.io", "subject": "FAILED: build #42", "labels": ["ci"]}
        constraints = {
            "sender_contains": "jenkins",
            "subject_matches": "FAILED.*#\\d+",
            "labels": "ci",
        }
        assert match_item(item, constraints)


# ---------------------------------------------------------------------------
# extract_items
# ---------------------------------------------------------------------------


class TestExtractItems:
    def test_gmail(self):
        result = {"emails": [{"id": "1"}, {"id": "2"}], "total_unread": 2}
        assert extract_items(result, "emails") == [{"id": "1"}, {"id": "2"}]

    def test_slack(self):
        result = {"messages": [{"channel": "general"}]}
        assert extract_items(result, "messages") == [{"channel": "general"}]

    def test_github(self):
        result = {"notifications": [{"repo": "jarvis"}]}
        assert extract_items(result, "notifications") == [{"repo": "jarvis"}]

    def test_missing_key(self):
        assert extract_items({}, "emails") == []


# ---------------------------------------------------------------------------
# evaluate_permissions
# ---------------------------------------------------------------------------


class TestEvaluatePermissions:
    def _make_perm(
        self, perm_id="p1", source="gmail", constraints=None, actions=None, max_matches=None
    ):
        return {
            "id": perm_id,
            "source": source,
            "constraints": constraints or {},
            "allowed_actions": actions or ["archive"],
            "max_matches": max_matches,
        }

    def test_max_matches_custom_cap(self):
        """A per-rule max_matches overrides the default circuit-breaker limit."""
        emails = [{"id": str(i), "sender": "jenkins@ci.com"} for i in range(10)]
        perms = [self._make_perm(constraints={"sender_contains": "jenkins"}, max_matches=8)]
        matched, unmatched = evaluate_permissions("gmail", {"emails": emails}, perms, "emails")
        assert len(matched) == 8
        assert len(unmatched) == 2

    def test_max_matches_zero_is_unlimited(self):
        """max_matches=0 disables the circuit breaker — all matches go through."""
        emails = [{"id": str(i), "sender": "jenkins@ci.com"} for i in range(20)]
        perms = [self._make_perm(constraints={"sender_contains": "jenkins"}, max_matches=0)]
        matched, unmatched = evaluate_permissions("gmail", {"emails": emails}, perms, "emails")
        assert len(matched) == 20
        assert unmatched == []

    def test_max_matches_none_uses_default(self):
        """max_matches=None falls back to MAX_MATCHES_PER_PERMISSION."""
        emails = [{"id": str(i), "sender": "jenkins@ci.com"} for i in range(10)]
        perms = [self._make_perm(constraints={"sender_contains": "jenkins"}, max_matches=None)]
        matched, _ = evaluate_permissions("gmail", {"emails": emails}, perms, "emails")
        assert len(matched) == MAX_MATCHES_PER_PERMISSION

    def test_basic_matching(self):
        result = {
            "emails": [
                {"id": "1", "sender": "jenkins@ci.com", "subject": "fail"},
                {"id": "2", "sender": "alice@team.com", "subject": "hello"},
            ]
        }
        perms = [self._make_perm(constraints={"sender_contains": "jenkins"})]
        matched, unmatched = evaluate_permissions("gmail", result, perms, "emails")
        assert len(matched) == 1
        assert len(unmatched) == 1
        assert matched[0]["id"] == "1"
        assert matched[0]["_permission"]["id"] == "p1"

    def test_no_permissions(self):
        result = {"emails": [{"id": "1", "sender": "anyone"}]}
        matched, unmatched = evaluate_permissions("gmail", result, [], "emails")
        assert matched == []
        assert len(unmatched) == 1

    def test_wrong_source_permission_ignored(self):
        result = {"emails": [{"id": "1", "sender": "jenkins@ci.com"}]}
        perms = [self._make_perm(source="slack", constraints={"sender_contains": "jenkins"})]
        matched, unmatched = evaluate_permissions("gmail", result, perms, "emails")
        assert matched == []
        assert len(unmatched) == 1

    def test_null_source_matches_any(self):
        result = {"emails": [{"id": "1", "sender": "jenkins@ci.com"}]}
        perms = [self._make_perm(source=None, constraints={"sender_contains": "jenkins"})]
        matched, unmatched = evaluate_permissions("gmail", result, perms, "emails")
        assert len(matched) == 1

    def test_first_matching_permission_wins(self):
        result = {"emails": [{"id": "1", "sender": "jenkins@ci.com", "subject": "fail"}]}
        perms = [
            self._make_perm(perm_id="p1", constraints={"sender_contains": "jenkins"}),
            self._make_perm(perm_id="p2", constraints={"subject_contains": "fail"}),
        ]
        matched, _ = evaluate_permissions("gmail", result, perms, "emails")
        assert len(matched) == 1
        assert matched[0]["_permission"]["id"] == "p1"

    def test_circuit_breaker(self):
        emails = [
            {"id": str(i), "sender": "jenkins@ci.com", "subject": f"Build {i}"} for i in range(10)
        ]
        result = {"emails": emails}
        perms = [self._make_perm(constraints={"sender_contains": "jenkins"})]
        matched, unmatched = evaluate_permissions("gmail", result, perms, "emails")
        assert len(matched) == MAX_MATCHES_PER_PERMISSION
        assert len(unmatched) == 10 - MAX_MATCHES_PER_PERMISSION

    def test_circuit_breaker_stops_matching_for_item(self):
        """When a permission hits its limit, excess items go to unmatched (safe default).

        Even if another permission could match, the circuit breaker halts evaluation
        for safety — prevents a broad fallback rule from acting on overflow items.
        """
        emails = [
            {"id": str(i), "sender": "jenkins@ci.com", "subject": f"Build {i}"} for i in range(10)
        ]
        result = {"emails": emails}
        perms = [
            self._make_perm(perm_id="p1", constraints={"sender_contains": "jenkins"}),
            self._make_perm(perm_id="p2", constraints={"subject_contains": "Build"}),
        ]
        matched, unmatched = evaluate_permissions("gmail", result, perms, "emails")
        # p1 matches first 5, then hits circuit breaker. Remaining items go unmatched.
        assert len(matched) == MAX_MATCHES_PER_PERMISSION
        assert len(unmatched) == 10 - MAX_MATCHES_PER_PERMISSION
        assert all(m["_permission"]["id"] == "p1" for m in matched)

    def test_independent_permissions_each_get_quota(self):
        """Permissions matching different items each get their own circuit breaker quota."""
        emails = [
            {"id": "j1", "sender": "jenkins@ci.com", "subject": "Build 1"},
            {"id": "j2", "sender": "jenkins@ci.com", "subject": "Build 2"},
            {"id": "a1", "sender": "alice@team.com", "subject": "Review request"},
        ]
        result = {"emails": emails}
        perms = [
            self._make_perm(perm_id="p1", constraints={"sender_contains": "jenkins"}),
            self._make_perm(perm_id="p2", constraints={"sender_contains": "alice"}),
        ]
        matched, unmatched = evaluate_permissions("gmail", result, perms, "emails")
        assert len(matched) == 3
        assert len(unmatched) == 0

    def test_empty_items(self):
        result = {"emails": []}
        perms = [self._make_perm(constraints={"sender_contains": "jenkins"})]
        matched, unmatched = evaluate_permissions("gmail", result, perms, "emails")
        assert matched == []
        assert unmatched == []


# ---------------------------------------------------------------------------
# check_circuit_breaker
# ---------------------------------------------------------------------------


class TestCheckCircuitBreaker:
    def test_no_overflow(self):
        result = {
            "emails": [
                {"id": "1", "sender": "jenkins@ci.com"},
                {"id": "2", "sender": "jenkins@ci.com"},
            ]
        }
        perms = [{"id": "p1", "source": "gmail", "constraints": {"sender_contains": "jenkins"}}]
        overflow = check_circuit_breaker("gmail", result, perms, "emails")
        assert overflow == {}

    def test_overflow_detected(self):
        emails = [{"id": str(i), "sender": "jenkins@ci.com"} for i in range(10)]
        result = {"emails": emails}
        perms = [{"id": "p1", "source": "gmail", "constraints": {"sender_contains": "jenkins"}}]
        overflow = check_circuit_breaker("gmail", result, perms, "emails")
        assert overflow == {"p1": 10}

    def test_at_limit_no_overflow(self):
        emails = [
            {"id": str(i), "sender": "jenkins@ci.com"} for i in range(MAX_MATCHES_PER_PERMISSION)
        ]
        result = {"emails": emails}
        perms = [{"id": "p1", "source": "gmail", "constraints": {"sender_contains": "jenkins"}}]
        overflow = check_circuit_breaker("gmail", result, perms, "emails")
        assert overflow == {}

    def test_just_over_limit(self):
        emails = [
            {"id": str(i), "sender": "jenkins@ci.com"}
            for i in range(MAX_MATCHES_PER_PERMISSION + 1)
        ]
        result = {"emails": emails}
        perms = [{"id": "p1", "source": "gmail", "constraints": {"sender_contains": "jenkins"}}]
        overflow = check_circuit_breaker("gmail", result, perms, "emails")
        assert overflow == {"p1": MAX_MATCHES_PER_PERMISSION + 1}
