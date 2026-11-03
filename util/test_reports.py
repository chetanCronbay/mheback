""""Send to all vendors" (monthly vendor reports): runs in the background, skips vendors who already
got this month's report, and reports its progress.

The background thread is run inline here, with Django's in-memory mail backend (no real email).
Run: python manage.py test util.test_reports
"""
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Role, User, Vendor
from util import reports


class InlineThread:
    """threading.Thread that runs its target as soon as it is started."""

    def __init__(self, target, args=(), kwargs=None, **_):
        self.target, self.args, self.kwargs = target, args, kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


@override_settings(
    ADMIN_EMAIL="contact@mhebazar.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
@mock.patch("util.reports.threading.Thread", InlineThread)
@mock.patch("util.reports.connections", mock.MagicMock())  # the inline "thread" shares the test's connection
class SendAllVendorReportsTests(TestCase):
    url = "/reports/send-all-vendors/"

    @classmethod
    def setUpTestData(cls):
        admin_role = Role.objects.create(id=Role.ADMIN, name="Admin")
        vendor_role = Role.objects.create(id=Role.VENDOR, name="Vendor")
        cls.admin = User.objects.create(username="admin", email="boss@example.com", role=admin_role)
        cls.vendors = []
        for i, email in enumerate(["one@vendor.com", "two@vendor.com", ""]):
            user = User.objects.create(username=f"vendor{i}", email=f"v{i}@x.com", role=vendor_role)
            cls.vendors.append(Vendor.objects.create(
                user=user, company_name=f"Vendor {i}", company_email=email,
                company_phone="+919876543210", company_address="Chennai",
            ))

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client.force_login(self.admin)

    def reports_sent(self):
        return [m for m in mail.outbox if m.subject.startswith("Your Monthly Performance Report")]

    def summaries(self):
        return [m for m in mail.outbox if m.subject.startswith("Vendor monthly reports:")]

    def test_sends_every_vendor_and_reports_the_result(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("vendor-report-dashboard"), fetch_redirect_response=False)

        self.assertEqual(sorted(m.to[0] for m in self.reports_sent()), ["one@vendor.com", "two@vendor.com"])
        status = cache.get(reports.BULK_STATUS_KEY)
        self.assertEqual((status["state"], status["total"], status["sent"]), ("finished", 3, 2))
        self.assertEqual(status["failed"], ["Vendor 2: no company email address"])
        self.assertIsNone(cache.get(reports.BULK_LOCK_KEY))  # the button is free again

        for report in self.reports_sent():
            self.assertIn("contact@mhebazar.com", report.cc)  # MHE's inbox gets a copy of every report

        [summary] = self.summaries()
        self.assertEqual(summary.to, ["contact@mhebazar.com", "boss@example.com"])
        self.assertIn("2 of 3 sent, 1 failed", summary.body)
        self.assertIn("Vendor 2: no company email address", summary.body)

    def test_sending_again_skips_vendors_who_already_got_it(self):
        self.client.post(self.url)
        mail.outbox = []
        self.client.post(self.url)
        self.assertEqual(self.reports_sent(), [])  # only the vendor without an email is tried again
        status = cache.get(reports.BULK_STATUS_KEY)
        self.assertEqual((status["total"], status["skipped"]), (1, 2))

    def test_resend_sends_to_everyone_again(self):
        self.client.post(self.url)
        mail.outbox = []
        self.client.post(self.url, {"resend": "1"})
        self.assertEqual(len(self.reports_sent()), 2)

    def test_single_send_counts_as_sent(self):
        self.client.post(f"/reports/send-vendor/{self.vendors[0].id}/")
        [single] = self.reports_sent()
        self.assertIn("contact@mhebazar.com", single.cc)  # one-by-one sends are copied too
        mail.outbox = []
        self.client.post(self.url)
        self.assertEqual([m.to[0] for m in self.reports_sent()], ["two@vendor.com"])

    def test_one_run_at_a_time(self):
        cache.set(reports.BULK_LOCK_KEY, self.admin.pk)
        response = self.client.post(self.url, follow=True)
        self.assertEqual(mail.outbox, [])
        self.assertContains(response, "already being sent")

    def test_a_failed_vendor_does_not_stop_the_others(self):
        real_send = reports._send_email
        calls = []

        def flaky_send(subject, template, context, to_emails, *args, **kwargs):
            calls.append(to_emails[0])
            if to_emails[0] == "one@vendor.com":
                raise ConnectionError("SMTP connection dropped")
            return real_send(subject, template, context, to_emails, *args, **kwargs)

        with mock.patch("util.reports._send_email", flaky_send):
            self.client.post(self.url)
        self.assertEqual([m.to[0] for m in self.reports_sent()], ["two@vendor.com"])
        status = cache.get(reports.BULK_STATUS_KEY)
        self.assertIn("Vendor 0: SMTP connection dropped", status["failed"])

    def test_dashboard_shows_the_progress(self):
        self.client.post(self.url)
        dashboard = self.client.get(reverse("vendor-report-dashboard"))
        self.assertContains(dashboard, "2 of 3 sent, 1 failed")
