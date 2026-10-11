import asyncio
from contextlib import nullcontext
from datetime import UTC, datetime
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, patch

from ankama_launcher_emulator.controller import (
    mail_account as mail_account_module,
)
from ankama_launcher_emulator.controller.mail_account import (
    MailAccountController,
)
from ankama_launcher_emulator.interfaces.mail_account import (
    MailAccountsFile,
    SmailProAccountConfig,
)
from ankama_launcher_emulator.web._client.mail_providers import (
    smailpro as smailpro_module,
)
from ankama_launcher_emulator.web._client.mail_providers.smailpro import (
    RandomMailboxKind,
    SmailProMailProvider,
    SmailProSettings,
    generate_random_mailbox,
)


def _response(json_body: dict[str, object]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = json_body
    response.raise_for_status.return_value = None
    return response


class TestGenerateRandomMailbox(TestCase):
    def test_calls_dedicated_random_endpoint_for_each_kind(self) -> None:
        cases: list[tuple[RandomMailboxKind, str]] = [
            ("gmail", "/v1/temp_gmail/random"),
            ("outlook", "/v1/temp_outlook/random"),
        ]
        for kind, expected_path in cases:
            with self.subTest(kind=kind):
                response = _response(
                    {"email": f"someone@{kind}.com", "timestamp": 1723680000, "type": "real"}
                )

                with patch("requests.Session.get", return_value=response) as get:
                    email, timestamp = generate_random_mailbox("api-key", kind)

                self.assertEqual(email, f"someone@{kind}.com")
                self.assertEqual(timestamp, 1723680000)
                get.assert_called_once()
                self.assertTrue(get.call_args.args[0].endswith(expected_path))
                self.assertEqual(get.call_args.kwargs["params"], {"type": "real"})

    def test_outlook_token_refresh_failure_disables_outlook_for_one_day(self) -> None:
        provider = SmailProMailProvider(
            SmailProSettings(
                api_key="api-key", email="temp@outlook.com", kind="outlook", timestamp=1723680000
            )
        )
        error = smailpro_module.HaapiHttpError(
            "Outlook token refresh failed: 400 unauthorized_client - AADSTS700016", 400
        )

        with (
            patch("requests.Session.get", return_value=_response({})),
            patch.object(smailpro_module, "raise_for_status_with_content", side_effect=error),
            patch.object(smailpro_module, "disable_outlook_generation") as disable_outlook_generation,
        ):
            with self.assertRaises(smailpro_module.HaapiHttpError):
                provider._recent_messages(datetime.now(UTC))

        disable_outlook_generation.assert_called_once_with()


class TestProvisionSmailProEmail(TestCase):
    def test_skips_available_outlook_mailboxes_during_outage(self) -> None:
        accounts_file = MailAccountsFile.model_validate(
            {
                "accounts": {
                    "someone@outlook.com": {
                        "config": {
                            "provider": "smailpro",
                            "api_key": "api-key",
                            "email": "someone@outlook.com",
                            "kind": "outlook",
                            "timestamp": 1723680000,
                        }
                    }
                }
            }
        )
        controller = MailAccountController()

        with (
            patch.object(controller, "_load", return_value=accounts_file),
            patch.object(mail_account_module, "is_outlook_generation_disabled", return_value=True),
        ):
            email = controller.peek_next_available_email()

        self.assertIsNone(email)

    def test_provisions_the_selected_real_mailbox(self) -> None:
        accounts_file = MailAccountsFile()
        controller = MailAccountController()

        with (
            patch.object(
                mail_account_module,
                "generate_random_mailbox_settings",
                return_value=SmailProSettings(
                    api_key="api-key",
                    email="someone@outlook.com",
                    kind="outlook",
                    timestamp=1723680000,
                ),
            ) as generate_random_mailbox_settings,
            patch.object(controller, "_acquire_file_lock", return_value=nullcontext()),
            patch.object(controller, "_load", return_value=accounts_file),
            patch.object(controller, "_save") as save,
        ):
            email = controller.provision_smailpro_email("api-key")

        self.assertEqual(email, "someone@outlook.com")
        generate_random_mailbox_settings.assert_called_once_with("api-key")
        save.assert_called_once_with(accounts_file)
        config = accounts_file.accounts[email].config
        assert isinstance(config, SmailProAccountConfig)
        self.assertEqual(config.kind, "outlook")


class TestSmailProMailProviderWaitForCode(IsolatedAsyncioTestCase):
    async def test_finds_code_from_recent_message(self) -> None:
        inbox_response = _response(
            {
                "messages": [
                    {
                        "mid": "m1",
                        "textFrom": "Ankama",
                        "textDate": "Thu, 18 Jun 2026 10:01:00 +0000",
                    },
                ]
            }
        )
        message_response = _response({"body": "Votre code de confirmation est 123456"})
        provider = SmailProMailProvider(
            SmailProSettings(api_key="api-key", email="temp@gmail.com", kind="gmail", timestamp=1723680000)
        )

        with (
            patch.object(smailpro_module, "SMAILPRO_INITIAL_DELAY_SECONDS", 0),
            patch("requests.Session.get", side_effect=[inbox_response, message_response]) as get,
            self.assertLogs(smailpro_module.logger, level="INFO") as logs,
        ):
            code = await provider.wait_for_code(
                since=datetime(2026, 6, 18, 10, 0, tzinfo=UTC), timeout_seconds=5
            )

        self.assertEqual(code, "123456")
        inbox_call = get.call_args_list[0]
        self.assertTrue(inbox_call.args[0].endswith("/v1/temp_gmail/inbox"))
        self.assertEqual(inbox_call.kwargs["params"]["timestamp"], 1781776790)
        self.assertEqual(len(logs.output), 1)

    def test_ignores_non_ankama_message_with_six_digit_tracking_identifier(self) -> None:
        inbox_response = _response(
            {
                "messages": [
                    {
                        "mid": "reddit",
                        "textFrom": "Reddit",
                        "textSubject": "Daily digest",
                        "textDate": "Thu, 18 Jun 2026 10:01:00 +0000",
                    },
                    {
                        "mid": "ankama",
                        "textSubject": "Votre code Ankama",
                        "textDate": "Thu, 18 Jun 2026 10:02:00 +0000",
                    },
                ]
            }
        )
        message_response = _response({"body": "Votre code de confirmation est 123456"})
        provider = SmailProMailProvider(
            SmailProSettings(api_key="api-key", email="temp@gmail.com", kind="gmail", timestamp=1723680000)
        )

        with patch("requests.Session.get", side_effect=[inbox_response, message_response]) as get:
            code = provider._find_code(since=datetime(2026, 6, 18, 10, 0, tzinfo=UTC))

        self.assertEqual(code, "123456")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].kwargs["params"]["mid"], "ankama")

    def test_uses_a_new_since_boundary_for_authentication_after_registration(self) -> None:
        registration_inbox = _response(
            {
                "messages": [
                    {"mid": "registration", "textFrom": "Ankama"},
                ]
            }
        )
        authentication_inbox = _response(
            {
                "messages": [
                    {"mid": "authentication", "textFrom": "Ankama"},
                ]
            }
        )
        provider = SmailProMailProvider(
            SmailProSettings(api_key="api-key", email="temp@gmail.com", kind="gmail", timestamp=1723680000)
        )

        with patch(
            "requests.Session.get",
            side_effect=[
                registration_inbox,
                _response({"body": "Code inscription 123456"}),
                authentication_inbox,
                _response({"body": "Code authentification 654321"}),
            ],
        ) as get:
            registration_code = provider._find_code(since=datetime(2026, 6, 18, 10, 0, tzinfo=UTC))
            authentication_code = provider._find_code(since=datetime(2026, 6, 18, 10, 5, tzinfo=UTC))

        self.assertEqual(registration_code, "123456")
        self.assertEqual(authentication_code, "654321")
        self.assertEqual(get.call_args_list[0].kwargs["params"]["timestamp"], 1781776790)
        self.assertEqual(get.call_args_list[2].kwargs["params"]["timestamp"], 1781777090)

    def test_recreated_provider_skips_registration_message_already_consumed(self) -> None:
        settings = SmailProSettings(
            api_key="api-key",
            email="temp@gmail.com",
            kind="gmail",
            timestamp=1723680000,
        )
        consumed_message_ids: list[str] = []
        registration_provider = SmailProMailProvider(
            SmailProSettings(
                api_key=settings.api_key,
                email=settings.email,
                kind=settings.kind,
                timestamp=settings.timestamp,
                mark_message_consumed=consumed_message_ids.append,
            )
        )
        registration_inbox = _response({"messages": [{"mid": "registration", "textFrom": "Ankama"}]})
        authentication_inbox = _response(
            {
                "messages": [
                    {"mid": "registration", "textFrom": "Ankama"},
                    {"mid": "authentication", "textFrom": "Ankama"},
                ]
            }
        )

        with patch(
            "requests.Session.get",
            side_effect=[
                registration_inbox,
                _response({"body": "Code inscription 123456"}),
                authentication_inbox,
                _response({"body": "Code authentification 654321"}),
            ],
        ) as get:
            registration_code = registration_provider._find_code(
                since=datetime(2026, 6, 18, 10, 0, tzinfo=UTC)
            )
            authentication_provider = SmailProMailProvider(
                SmailProSettings(
                    api_key=settings.api_key,
                    email=settings.email,
                    kind=settings.kind,
                    timestamp=settings.timestamp,
                    consumed_message_ids=frozenset(consumed_message_ids),
                )
            )
            authentication_code = authentication_provider._find_code(
                since=datetime(2026, 6, 18, 10, 5, tzinfo=UTC)
            )

        self.assertEqual(registration_code, "123456")
        self.assertEqual(authentication_code, "654321")
        self.assertEqual(consumed_message_ids, ["registration"])
        self.assertEqual(get.call_args_list[3].kwargs["params"]["mid"], "authentication")

    async def test_caps_paid_inbox_wait(self) -> None:
        provider = SmailProMailProvider(
            SmailProSettings(api_key="api-key", email="temp@gmail.com", kind="gmail", timestamp=1723680000)
        )

        with (
            patch.object(provider, "_find_code", return_value=None),
            patch.object(smailpro_module, "SMAILPRO_CODE_TIMEOUT_SECONDS", 0.03),
            patch.object(smailpro_module, "SMAILPRO_INITIAL_DELAY_SECONDS", 0.01),
            patch.object(smailpro_module, "SMAILPRO_POLL_INTERVAL_SECONDS", 0.01),
        ):
            code = await asyncio.wait_for(
                provider.wait_for_code(since=datetime(2026, 6, 18, 10, 0, tzinfo=UTC), timeout_seconds=1200),
                timeout=0.2,
            )

        self.assertIsNone(code)
