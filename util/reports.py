from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import connections
from django.db.models import Count, Q

from products.models import Product, Quote, Rental
from users.models import User, Vendor, Role
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

# --- STATIC ASSETS ---
MHE_WEBSITE_URL = "https://api.mhebazar.in"
MHE_LOGO_URL = "https://www.mhebazar.in/mhe-logo.png"

# --- BULK VENDOR REPORTS ---
# "Send to all vendors" emails every vendor one by one, which takes longer than a web request may
# run (gunicorn stops it after 30 seconds). So it runs in a background thread over one mail
# connection, and the dashboard shows its progress. Each vendor sent this month's report is
# remembered (in the shared cache), so sending again skips them unless "resend" is ticked.
BULK_LOCK_KEY = 'vendor_reports:bulk_running'
BULK_STATUS_KEY = 'vendor_reports:bulk_status'
BULK_LOCK_SECONDS = 60 * 60          # a stuck run frees the button after an hour
BULK_STATUS_SECONDS = 7 * 24 * 3600  # the dashboard shows the last run for a week
SENT_MARKER_SECONDS = 45 * 24 * 3600
SMTP_TIMEOUT_SECONDS = 30


def _report_period(date_ranges):
    """The month a monthly report covers: '2026-10'."""
    return date_ranges['last_month_start'].strftime('%Y-%m')


def _sent_key(period, vendor_id):
    return f'vendor_reports:sent:{period}:{vendor_id}'


def _admin_emails():
    """MHE's own inbox for report copies and summaries: ADMIN_EMAIL (contact@mhebazar.com), as a list."""
    admin = settings.ADMIN_EMAIL
    return [admin] if isinstance(admin, str) else list(admin)

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role.id == Role.ADMIN)

def _get_date_ranges():
    today = timezone.now().date()
    # Last Week: Previous Monday to Sunday
    start_of_week = today - timedelta(days=today.weekday())
    last_week_start = start_of_week - timedelta(weeks=1)
    last_week_end = start_of_week - timedelta(days=1)
    
    # Last Month: 1st to last day of previous month
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    return {
        'today': today,
        'last_week_start': last_week_start,
        'last_week_end': last_week_end,
        'last_month_start': last_month_start,
        'last_month_end': last_month_end
    }

def _get_product_stats(products_queryset, date_ranges):
    """
    Calculate detailed product stats for a given queryset of products.
    Returns a dictionary with total counts and categorized counts.
    """
    # Filter for approved products only
    approved_products = products_queryset.filter(status='approved')
    
    # Last Month Approved
    last_month_approved = approved_products.filter(
        created_at__date__gte=date_ranges['last_month_start'],
        created_at__date__lte=date_ranges['last_month_end']
    )

    def count_by_type(queryset):
        return {
            'new': queryset.filter(type__contains='new').count(),
            'used': queryset.filter(type__contains='used').count(),
            'rental': queryset.filter(type__contains='rental').count(),
            'attachments': queryset.filter(type__contains='attachments').count(),
        }

    return {
        'total_approved': approved_products.count(),
        'last_month_approved_count': last_month_approved.count(),
        'total_by_type': count_by_type(approved_products),
        'last_month_by_type': count_by_type(last_month_approved),
    }


def _load_getdata_counts():
    """Load `getdata.json` (if present) and return a mapping product_id -> occurrence count.

    This is defensive: if the file doesn't exist or parsing fails, return an empty dict.
    """
    try:
        base_dir = getattr(settings, 'BASE_DIR', None)
        if base_dir:
            path = os.path.join(base_dir, 'getdata.json')
        else:
            path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'getdata.json'))

        if not os.path.exists(path):
            return {}

        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)

        # `getdata.json` may be in multiple shapes depending on export:
        # - phpMyAdmin exports as a list containing a 'table' element with a 'data' list
        # - or it may be a dict with a top-level 'data' list
        # - or it may already be a flat list of row objects
        rows = []
        if isinstance(data, dict) and isinstance(data.get('data'), list):
            rows = data.get('data')
        elif isinstance(data, list):
            # Collect any nested 'data' lists, else treat top-level dicts as rows
            for elem in data:
                if isinstance(elem, dict) and isinstance(elem.get('data'), list):
                    rows.extend(elem.get('data'))
                elif isinstance(elem, dict) and any(k in elem for k in ('product_id', 'productId', 'prod_id')):
                    rows.append(elem)
        elif isinstance(data, dict):
            # last fallback: treat whole dict as a row
            rows = [data]

        counts = {}
        for item in rows:
            if not isinstance(item, dict):
                continue
            pid = item.get('product_id') or item.get('productId') or item.get('prod_id')
            if pid is None:
                continue
            try:
                pid = int(pid)
            except Exception:
                continue
            counts[pid] = counts.get(pid, 0) + 1

        return counts
    except Exception:
        return {}

def _get_vendor_stats(user, date_ranges, getdata_counts=None):
    """Calculate stats for a specific vendor user. `getdata_counts`: _load_getdata_counts(), if already loaded."""
    # Get all products for this vendor
    products = Product.objects.filter(user=user)
    
    # Base queries
    quotes = Quote.objects.filter(product__in=products)
    rentals = Rental.objects.filter(product__in=products)
    
    # Product Stats
    product_stats = _get_product_stats(products, date_ranges)

    stats = {
        # include getdata.json counts for this vendor's products
        'total_quotes': quotes.count(),
        'total_rentals': rentals.count(),
        
        'quotes_last_month': quotes.filter(
            created_at__date__gte=date_ranges['last_month_start'],
            created_at__date__lte=date_ranges['last_month_end']
        ).count(),
        
        'rentals_last_month': rentals.filter(
            created_at__date__gte=date_ranges['last_month_start'],
            created_at__date__lte=date_ranges['last_month_end']
        ).count(),
        
        'quotes_last_week': quotes.filter(
            created_at__date__gte=date_ranges['last_week_start'],
            created_at__date__lte=date_ranges['last_week_end']
        ).count(),
        
        'rentals_last_week': rentals.filter(
            created_at__date__gte=date_ranges['last_week_start'],
            created_at__date__lte=date_ranges['last_week_end']
        ).count(),
        
        # Merge product stats
        **product_stats
    }
    # Add counts from getdata.json only to the `total_quotes` value
    try:
        if getdata_counts is None:
            getdata_counts = _load_getdata_counts()
        if getdata_counts:
            product_ids = list(products.values_list('id', flat=True))
            extra = 0
            for pid in product_ids:
                extra += getdata_counts.get(pid, 0)
            stats['total_quotes'] = stats.get('total_quotes', 0) + extra
    except Exception:
        # conservative: if loading/parsing fails, leave DB-derived counts as-is
        pass

    return stats

def _get_dashboard_context():
    date_ranges = _get_date_ranges()
    
    # 1. Overall Stats
    # Base DB counts
    total_quotes = Quote.objects.count()
    total_rentals = Rental.objects.count()

    # Add counts from getdata.json for products that exist in our DB
    try:
        getdata_counts = _load_getdata_counts()
        if getdata_counts:
            # keep only product ids that exist in our Product table
            existing_ids = set(Product.objects.filter(id__in=list(getdata_counts.keys())).values_list('id', flat=True))
            extra_total = sum(getdata_counts.get(pid, 0) for pid in existing_ids)
            total_quotes = total_quotes + extra_total
    except Exception:
        # ignore and use DB counts only
        pass
    
    quotes_last_month = Quote.objects.filter(
        created_at__date__gte=date_ranges['last_month_start'],
        created_at__date__lte=date_ranges['last_month_end']
    ).count()
    
    rentals_last_month = Rental.objects.filter(
        created_at__date__gte=date_ranges['last_month_start'],
        created_at__date__lte=date_ranges['last_month_end']
    ).count()
    
    quotes_last_week = Quote.objects.filter(
        created_at__date__gte=date_ranges['last_week_start'],
        created_at__date__lte=date_ranges['last_week_end']
    ).count()
    
    rentals_last_week = Rental.objects.filter(
        created_at__date__gte=date_ranges['last_week_start'],
        created_at__date__lte=date_ranges['last_week_end']
    ).count()
    
    # Overall Product Stats
    all_products = Product.objects.all()
    overall_product_stats = _get_product_stats(all_products, date_ranges)

    overall_stats = {
        'total_quotes': total_quotes,
        'total_rentals': total_rentals,
        'quotes_last_month': quotes_last_month,
        'rentals_last_month': rentals_last_month,
        'quotes_last_week': quotes_last_week,
        'rentals_last_week': rentals_last_week,
        **overall_product_stats
    }

    # 2. Vendor List
    # Get users who have a Vendor profile AND are active AND have the Vendor role
    vendors = Vendor.objects.select_related('user').filter(
        user__role__id=Role.VENDOR,
        user__is_active=True
    ).all()
    
    vendor_list = []
    getdata_counts = _load_getdata_counts()
    for vendor in vendors:
        user = vendor.user
        stats = _get_vendor_stats(user, date_ranges, getdata_counts)
        
        # Get logo from user profile
        logo_url = MHE_LOGO_URL
        if user.profile_photo:
            logo_url = user.profile_photo.url
            
        vendor_data = {
            'id': vendor.id,
            'user_id': user.id,
            'company_name': vendor.company_name,
            'name': user.get_full_name(),
            'email': vendor.company_email, # Use company email for reports
            'phone': vendor.company_phone,
            'logo_url': logo_url,
            'stats': stats
        }
        vendor_list.append(vendor_data)
        
    return {
        'overall_stats': overall_stats,
        'vendors': vendor_list,
        'date_ranges': date_ranges,
        'MHE_LOGO_URL': MHE_LOGO_URL
    }

@user_passes_test(is_admin)
def vendor_report_dashboard(request):
    context = _get_dashboard_context()
    context['bulk_status'] = cache.get(BULK_STATUS_KEY)
    return render(request, 'reports/vendor_report_dashboard.html', context)

# --- PREVIEW VIEWS ---

@user_passes_test(is_admin)
def preview_admin_report(request, report_type):
    """Preview the admin report before sending."""
    context = _get_dashboard_context()
    date_ranges = context['date_ranges']
    
    if report_type == 'weekly':
        period_name = "Last Week"
        start_date = date_ranges['last_week_start']
        end_date = date_ranges['last_week_end']
    else:
        period_name = "Last Month"
        start_date = date_ranges['last_month_start']
        end_date = date_ranges['last_month_end']

    email_context = {
        'overall_stats': context['overall_stats'],
        'vendors': context['vendors'],
        'period_name': period_name,
        'start_date': start_date,
        'end_date': end_date,
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'report_type': report_type
    }
    
    # Render the email HTML
    email_html = render_to_string('reports/admin_report_email.html', email_context)
    
    return render(request, 'reports/report_preview.html', {
        'email_html': email_html,
        'action_url': f"/reports/send-admin/{report_type}/",
        'title': f"Preview Admin {report_type.title()} Report",
        'recipient_list': ['ulhas.makeshwar@greentechmh.com', 'manik.thapar@greentechmh.com', 'sumedh.ramteke@mhebazar.com', 'rakesh.a@greentechmh.com', 'marketing.1@mhebazar.com','developer@cronbaytechnologies.com']
    })

@user_passes_test(is_admin)
def preview_vendor_report(request, vendor_id):
    """Preview a single vendor report."""
    vendor = get_object_or_404(Vendor, id=vendor_id)
    user = vendor.user
    date_ranges = _get_date_ranges()
    stats = _get_vendor_stats(user, date_ranges)
    
    logo_url = MHE_LOGO_URL
    if user.profile_photo:
         if user.profile_photo.url.startswith('http'):
            logo_url = user.profile_photo.url
         else:
            logo_url = f"{MHE_WEBSITE_URL}{user.profile_photo.url}"

    email_context = {
        'vendor_name': vendor.company_name,
        'contact_name': user.get_full_name(),
        'stats': stats,
        'period_name': date_ranges['last_month_start'].strftime('%B %Y'),
        'start_date': date_ranges['last_month_start'],
        'end_date': date_ranges['last_month_end'],
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'VENDOR_LOGO_URL': logo_url,
        'plan_name': "Plan-Gold (OEM)"
    }
    
    email_html = render_to_string('reports/vendor_monthly_report_email.html', email_context)
    
    return render(request, 'reports/report_preview.html', {
        'email_html': email_html,
        'action_url': f"/reports/send-vendor/{vendor.id}/",
        'title': f"Preview Report for {vendor.company_name}",
        'recipient_list': [vendor.company_email, 'sumedh.ramteke@mhebazar.com', 'rakesh.a@greentechmh.com', 'marketing.1@mhebazar.com','developer@cronbaytechnologies.com', *_admin_emails()]
    })

@user_passes_test(is_admin)
def preview_all_vendor_reports(request):
    """Preview all vendor reports in a list."""
    # Filter: Role=Vendor (2) AND Active=True
    vendors = Vendor.objects.select_related('user').filter(
        user__role__id=Role.VENDOR,
        user__is_active=True
    ).all()
    
    date_ranges = _get_date_ranges()
    period = _report_period(date_ranges)
    getdata_counts = _load_getdata_counts()

    previews = []
    all_recipients = []
    already_sent = []

    for vendor in vendors:
        user = vendor.user
        stats = _get_vendor_stats(user, date_ranges, getdata_counts)
        if cache.get(_sent_key(period, vendor.id)):
            already_sent.append(vendor.company_name)
        
        logo_url = MHE_LOGO_URL
        if user.profile_photo:
             if user.profile_photo.url.startswith('http'):
                logo_url = user.profile_photo.url
             else:
                logo_url = f"{MHE_WEBSITE_URL}{user.profile_photo.url}"

        email_context = {
            'vendor_name': vendor.company_name,
            'contact_name': user.get_full_name(),
            'stats': stats,
            'period_name': date_ranges['last_month_start'].strftime('%B %Y'),
            'start_date': date_ranges['last_month_start'],
            'end_date': date_ranges['last_month_end'],
            'MHE_LOGO_URL': MHE_LOGO_URL,
            'VENDOR_LOGO_URL': logo_url,
            'plan_name': "Plan-Gold (OEM)"
        }
        
        email_html = render_to_string('reports/vendor_monthly_report_email.html', email_context)
        previews.append({
            'vendor_name': vendor.company_name,
            'html': email_html
        })
        all_recipients.append(vendor.company_email)

    # Add CCs to the recipient list display (just once to show they are included)
    all_recipients.extend(['(CC) sumedh.ramteke@mhebazar.com', '(CC) rakesh.a@greentechmh.com', '(CC) marketing.1@mhebazar.com','(cc) developer@cronbaytechnologies.com',
                           *(f'(CC) {email}' for email in _admin_emails())])

    return render(request, 'reports/report_preview_bulk.html', {
        'previews': previews,
        'action_url': "/reports/send-all-vendors/",
        'title': "Preview All Vendor Monthly Reports",
        'recipient_list': all_recipients,
        'already_sent': already_sent,
        'bulk_running': bool(cache.get(BULK_LOCK_KEY)),
    })


# --- SENDING VIEWS (Modified to handle POST) ---

def _send_email(subject, template_name, context, to_emails, cc_emails=None, reply_to=None, connection=None):
    html_content = render_to_string(template_name, context)
    text_content = "Please view this email in an HTML compatible viewer."

    msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, to_emails, cc=cc_emails,
                                 reply_to=reply_to, connection=connection)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

@user_passes_test(is_admin)
def send_admin_report(request, report_type):
    if request.method != 'POST':
        return redirect('vendor-report-dashboard')

    context = _get_dashboard_context()
    date_ranges = context['date_ranges']
    
    if report_type == 'weekly':
        subject = f"MHE Bazar Weekly Admin Report ({date_ranges['last_week_start']} - {date_ranges['last_week_end']})"
        period_name = "Last Week"
        start_date = date_ranges['last_week_start']
        end_date = date_ranges['last_week_end']
    else:
        subject = f"MHE Bazar Monthly Admin Report ({date_ranges['last_month_start'].strftime('%B %Y')})"
        period_name = "Last Month"
        start_date = date_ranges['last_month_start']
        end_date = date_ranges['last_month_end']

    email_context = {
        'overall_stats': context['overall_stats'],
        'vendors': context['vendors'],
        'period_name': period_name,
        'start_date': start_date,
        'end_date': end_date,
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'report_type': report_type
    }
    
    to_emails = ['ulhas.makeshwar@greentechmh.com']
    cc_emails = [
        'manik.thapar@greentechmh.com',
        'sumedh.ramteke@mhebazar.com',
        'rakesh.a@greentechmh.com',
        'marketing.1@mhebazar.com',
        'developer@cronbaytechnologies.com'
    ]
    
    try:
        _send_email(subject, 'reports/admin_report_email.html', email_context, to_emails, cc_emails)
        messages.success(request, f"Admin {report_type} report sent successfully.")
    except Exception as e:
        messages.error(request, f"Failed to send admin report: {str(e)}")
        
    return redirect('vendor-report-dashboard')

@user_passes_test(is_admin)
def send_vendor_report(request, vendor_id):
    if request.method != 'POST':
        return redirect('vendor-report-dashboard')

    try:
        vendor = Vendor.objects.select_related('user').get(id=vendor_id)
        _send_single_vendor_report(vendor)
        messages.success(request, f"Report sent to {vendor.company_name}.")
        
    except Vendor.DoesNotExist:
        messages.error(request, "Vendor not found.")
    except Exception as e:
        messages.error(request, f"Failed to send report to vendor {vendor_id}: {str(e)}")
        
    return redirect('vendor-report-dashboard')

@user_passes_test(is_admin)
def send_all_vendor_reports(request):
    """Start emailing this month's report to every active vendor, in the background (see BULK_LOCK_KEY)."""
    if request.method != 'POST':
        return redirect('vendor-report-dashboard')

    # Filter: Role=Vendor (2) AND Active=True
    vendor_ids = list(Vendor.objects.filter(
        user__role__id=Role.VENDOR,
        user__is_active=True
    ).order_by('id').values_list('id', flat=True))

    period = _report_period(_get_date_ranges())
    skipped = 0
    if request.POST.get('resend') != '1':
        pending = [vendor_id for vendor_id in vendor_ids if not cache.get(_sent_key(period, vendor_id))]
        skipped = len(vendor_ids) - len(pending)
        vendor_ids = pending
    if not vendor_ids:
        messages.info(request, "Every vendor has already been sent this month's report. Nothing was sent.")
        return redirect('vendor-report-dashboard')

    # One run at a time (a double click, or two admins at once)
    if not cache.add(BULK_LOCK_KEY, request.user.pk, timeout=BULK_LOCK_SECONDS):
        messages.warning(request, "Vendor reports are already being sent. The progress is shown below.")
        return redirect('vendor-report-dashboard')

    cache.set(BULK_STATUS_KEY, {
        'state': 'running', 'total': len(vendor_ids), 'sent': 0, 'failed': [], 'skipped': skipped,
        'started_at': timezone.now(), 'finished_at': None,
    }, timeout=BULK_STATUS_SECONDS)
    # Not a daemon thread: a worker that is asked to stop (reload) lets it finish first
    threading.Thread(
        target=_send_vendor_reports_in_background,
        args=(vendor_ids, request.user.email),
        name='vendor-reports',
    ).start()

    note = f" {skipped} vendor(s) already had this month's report and were skipped." if skipped else ""
    messages.success(
        request,
        f"Sending this month's report to {len(vendor_ids)} vendor(s) in the background.{note} "
        f"This page shows the progress; a summary is emailed to {request.user.email or 'you'} when it's done."
    )
    return redirect('vendor-report-dashboard')


def _send_vendor_reports_in_background(vendor_ids, notify_email):
    """Email each vendor's report over one mail connection, updating BULK_STATUS_KEY as it goes."""
    status = cache.get(BULK_STATUS_KEY) or {
        'state': 'running', 'total': len(vendor_ids), 'sent': 0, 'failed': [], 'skipped': 0,
        'started_at': timezone.now(), 'finished_at': None,
    }
    mail = None
    try:
        date_ranges = _get_date_ranges()
        getdata_counts = _load_getdata_counts()
        mail = get_connection(timeout=SMTP_TIMEOUT_SECONDS)
        vendors = Vendor.objects.select_related('user').filter(id__in=vendor_ids).order_by('id')
        for vendor in vendors:
            try:
                _send_single_vendor_report(vendor, connection=mail, date_ranges=date_ranges, getdata_counts=getdata_counts)
                status['sent'] += 1
            except Exception as error:
                logger.exception("Monthly report to vendor %s (%s) failed", vendor.id, vendor.company_name)
                status['failed'].append(f"{vendor.company_name}: {error}")
                try:
                    mail.close()  # the next vendor starts a fresh connection
                except Exception:
                    pass
            cache.set(BULK_STATUS_KEY, status, timeout=BULK_STATUS_SECONDS)
    except Exception as error:
        logger.exception("Bulk vendor report send stopped early")
        status['failed'].append(f"Stopped early: {error}")
    finally:
        if mail is not None:
            try:
                mail.close()
            except Exception:
                pass
        status['state'] = 'finished'
        status['finished_at'] = timezone.now()
        cache.set(BULK_STATUS_KEY, status, timeout=BULK_STATUS_SECONDS)
        cache.delete(BULK_LOCK_KEY)
        _email_bulk_summary(status, notify_email)
        connections.close_all()  # this thread's database connection


def _email_bulk_summary(status, notify_email):
    """Tell MHE's inbox (ADMIN_EMAIL) and the admin who started the run how it went."""
    recipients = list(dict.fromkeys(email for email in [*_admin_emails(), notify_email] if email))
    if not recipients:
        return
    failed = status['failed']
    lines = [
        f"Monthly vendor reports: {status['sent']} of {status['total']} sent, {len(failed)} failed.",
    ]
    if status.get('skipped'):
        lines.append(f"{status['skipped']} vendor(s) already had this month's report and were skipped.")
    if failed:
        lines += ["", "Not sent:"] + [f"- {item}" for item in failed]
        lines += ["", "Send these one by one from the Vendor Reporting Dashboard, or run 'Send to all' again "
                      "(vendors who already got the report are skipped)."]
    try:
        send_mail(
            f"Vendor monthly reports: {status['sent']} sent, {len(failed)} failed",
            "\n".join(lines), settings.DEFAULT_FROM_EMAIL, recipients,
        )
    except Exception:
        logger.exception("Couldn't email the bulk vendor report summary")


def _send_single_vendor_report(vendor, connection=None, date_ranges=None, getdata_counts=None):
    """Email one vendor last month's report, and remember that they got it (see _sent_key)."""
    if not (vendor.company_email or '').strip():
        raise ValueError("no company email address")
    user = vendor.user
    date_ranges = date_ranges or _get_date_ranges()
    stats = _get_vendor_stats(user, date_ranges, getdata_counts)
    
    subject = f"Your Monthly Performance Report - {date_ranges['last_month_start'].strftime('%B %Y')} - MHE Bazar"
    
    logo_url = MHE_LOGO_URL
    if user.profile_photo:
         if user.profile_photo.url.startswith('http'):
            logo_url = user.profile_photo.url
         else:
            logo_url = f"{MHE_WEBSITE_URL}{user.profile_photo.url}"

    email_context = {
        'vendor_name': vendor.company_name,
        'contact_name': user.get_full_name(),
        'stats': stats,
        'period_name': date_ranges['last_month_start'].strftime('%B %Y'),
        'start_date': date_ranges['last_month_start'],
        'end_date': date_ranges['last_month_end'],
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'VENDOR_LOGO_URL': logo_url,
        'plan_name': "Plan-Gold (OEM)"
    }
    
    to_emails = [vendor.company_email]
    cc_emails = [
        'sumedh.ramteke@mhebazar.com',
        'rakesh.a@greentechmh.com',
        'marketing.1@mhebazar.com',
        'developer@cronbaytechnologies.com',
        *_admin_emails(),  # contact@mhebazar.com
    ]

    _send_email(subject, 'reports/vendor_monthly_report_email.html', email_context, to_emails, cc_emails, connection=connection)
    cache.set(_sent_key(_report_period(date_ranges), vendor.id), timezone.now().isoformat(), timeout=SENT_MARKER_SECONDS)